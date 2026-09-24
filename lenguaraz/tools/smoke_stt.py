# SPDX-License-Identifier: Apache-2.0
"""``make smoke-stt``: transcribe a bundled sample with the real Gemini engine.

Uses quota (Constitution Art. XII.2: never in the test suite). Prints the finals, the word
error rate against the reference transcript, speech-to-caption latency percentiles measured
against the sample's sentence boundaries, token usage and an estimated cost, then appends a
dated row to ``docs/metrics.md``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from lenguaraz.config import (
    ConfigError,
    EngineKind,
    Settings,
    StageConfig,
    StagesFile,
    VadMode,
    load_settings,
)
from lenguaraz.glossary.auto import GeminiAutoGlossary, merge_glossary
from lenguaraz.ingest import open_source
from lenguaraz.logsetup import configure_logging
from lenguaraz.metrics import percentile
from lenguaraz.models import StageState
from lenguaraz.stt.gemini import GeminiSttEngine
from lenguaraz.stt.session import ManagedSttSession, Segment

METRICS_FILE = Path("docs/metrics.md")
METRICS_INTRO = (
    "# Metrics\n\n"
    "Measured by the project's own tooling (Constitution Art. V.2); definitions in this file."
    "\n\n## smoke-stt runs\n\n"
)
METRICS_HEADER = (
    "| Date (UTC) | Sample | Mode | Finals | WER | First partial p50/p95 ms | "
    "Utterance-to-final p50/p95 ms | Commit delay p50/p95 ms | Tokens (in/out) | "
    "Est. cost USD |\n"
    "|---|---|---|---|---|---|---|---|---|---|\n"
)
WER_LIMIT = 0.25
AUDIO_TOKENS_PER_SECOND = 25  # GT-6.1
PRICE_IN_PER_M = 3.50  # USD per 1M audio tokens (GT-6.1, pricing read 2026-09-22)
PRICE_OUT_PER_M = 21.0  # USD per 1M text tokens


def normalize(text: str) -> list[str]:
    return re.sub(r"[^\w\s]", " ", text.lower()).split()


def word_error_rate(reference: str, hypothesis: str) -> float:
    ref, hyp = normalize(reference), normalize(hypothesis)
    if not ref:
        return 0.0
    try:
        import jiwer

        return float(jiwer.wer(" ".join(ref), " ".join(hyp)))
    except ImportError:  # pragma: no cover - jiwer is a dev dependency
        return _levenshtein(ref, hyp) / len(ref)


def _levenshtein(a: list[str], b: list[str]) -> int:
    previous = list(range(len(b) + 1))
    for i, word in enumerate(a, 1):
        current = [i]
        for j, other in enumerate(b, 1):
            cost = previous[j - 1] + (word != other)
            current.append(min(previous[j] + 1, current[j - 1] + 1, cost))
        previous = current
    return previous[-1]


def utterance_latencies(
    boundaries: list[dict[str, float]], finals: list[tuple[float, Segment]], start_wall: float
) -> list[int]:
    """Sentence end → final caption, matching finals to boundaries in order."""
    out: list[int] = []
    for boundary, (wall, _segment) in zip(boundaries, finals, strict=False):
        end_wall = start_wall + boundary["end_ms"] / 1000.0
        out.append(max(0, round((wall - end_wall) * 1000)))
    return out


def first_partial_latencies(
    boundaries: list[dict[str, float]],
    finals: list[tuple[float, Segment]],
    interims: list[tuple[float, Segment]],
    start_wall: float,
) -> list[int]:
    """Sentence start → first partial caption of the utterance that ends with final k."""
    out: list[int] = []
    for boundary, (_wall, final) in zip(boundaries, finals, strict=False):
        firsts = [wall for wall, seg in interims if seg.seq == final.seq]
        if not firsts:
            continue
        start = start_wall + boundary["start_ms"] / 1000.0
        out.append(max(0, round((min(firsts) - start) * 1000)))
    return out


def estimate_cost(audio_seconds: float, response_tokens: int, hypothesis: str) -> float:
    tokens_out = response_tokens or len(hypothesis) / 4
    audio_cost = audio_seconds * AUDIO_TOKENS_PER_SECOND / 1e6 * PRICE_IN_PER_M
    return audio_cost + tokens_out / 1e6 * PRICE_OUT_PER_M


def read_reference(sample: Path) -> str:
    path = sample.with_suffix(".txt")
    if not path.is_file():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
    return " ".join(line.strip() for line in lines if line.strip() and not line.startswith("#"))


def read_boundaries(sample: Path) -> list[dict[str, float]]:
    path = sample.with_suffix(".json")
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("sentences", []))


def fmt_p(values: list[int]) -> str:
    return f"{percentile(values, 50)}/{percentile(values, 95)}" if values else "n/a"


async def run(
    sample: Path,
    stage: StageConfig,
    mode: str | None,
    verbose: bool = False,
    rotate: int | None = None,
    glossary: str = "manual",
) -> int:
    settings = load_settings(**({"stt_mode": mode} if mode else {}))
    if settings.engine is not EngineKind.GEMINI:
        raise ConfigError("smoke-stt needs ENGINE=gemini and a GEMINI_API_KEY in .env")
    configure_logging(settings.log_level)
    stage, glossary_label = await apply_glossary_option(stage, glossary, settings)
    print(f"glossary: {glossary_label} -> {stage.glossary}")
    reference = read_reference(sample)
    boundaries = read_boundaries(sample)

    engine = GeminiSttEngine(settings)
    interims: list[tuple[float, Segment]] = []
    finals: list[tuple[float, Segment]] = []
    start_wall = time.monotonic()

    rotation_marks: list[tuple[int, int]] = []  # (rotation number, t_audio_ms of its first caption)
    seen_rotations = 0

    def emit(segment: Segment) -> None:
        nonlocal seen_rotations
        now = time.monotonic()
        if session.stats.rotations > seen_rotations:
            seen_rotations = session.stats.rotations
            rotation_marks.append((seen_rotations, segment.t_audio_ms))
        stamp = f"{segment.t_audio_ms / 1000:6.1f}s +{segment.latency_ms:4d}ms"
        if segment.is_final:
            finals.append((now, segment))
            print(f"\n[final   {stamp}] {segment.text}")
        else:
            interims.append((now, segment))
            print(f"[interim {stamp}] {segment.text[-70:]}", end="\n" if verbose else "\r")

    def on_state(state: StageState, detail: str | None) -> None:
        print(f"\n[state] {state.value} {detail or ''}")

    session = ManagedSttSession(
        stage,
        engine,
        emit=emit,
        on_state=on_state,
        rotate_seconds=float(rotate or settings.session_rotate_seconds),
        stall_seconds=float(settings.stt_stall_seconds),
        vad_silence_ms=settings.vad_silence_ms if settings.vad_mode is VadMode.HYBRID else None,
        vad_threshold=settings.vad_threshold,
        drain_seconds=settings.rotation_drain_seconds,
        dedupe_window=settings.dedupe_window_seconds,
        swap_max_wait=settings.rotation_swap_max_wait_seconds,
    )
    queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=50)
    source = open_source(str(sample), ffmpeg_bin=settings.ffmpeg_bin, realtime=True, loop=False)

    anchor: list[float] = []  # wall time of the first chunk read from the source

    async def pump() -> None:
        try:
            async for chunk in source.chunks():
                if not anchor:
                    anchor.append(time.monotonic())
                await queue.put(chunk)
        finally:
            await queue.put(None)

    pump_task = asyncio.create_task(pump())
    try:
        await session.run(queue)
    finally:
        pump_task.cancel()
        await source.close()

    hypothesis = " ".join(segment.text for _, segment in finals)
    wer = word_error_rate(reference, hypothesis) if reference else float("nan")
    final_lat = [s.latency_ms for _, s in finals]
    stream_start = anchor[0] if anchor else (session.stream_start or start_wall)
    utt = utterance_latencies(boundaries, finals, stream_start)
    first = first_partial_latencies(boundaries, finals, interims, stream_start)
    stats = session.stats
    audio_seconds = stats.bytes_sent / 32_000
    cost = estimate_cost(audio_seconds, stats.response_tokens, hypothesis)

    print("\n=== smoke-stt summary ===")
    print(f"sample: {sample}  mode: {settings.stt_mode.value}  model: {settings.gemini_stt_model}")
    print(f"glossary: {glossary_label}")
    print(f"finals: {len(finals)}  interims: {len(interims)}  sessions: {stats.sessions_opened}")
    print(f"errors: {stats.errors}  rotations: {stats.rotations}  vad_signals: {stats.vad_signals}")
    if rotate:
        expected = len(boundaries) if boundaries else None
        lost = (expected - len(finals)) if expected is not None else "n/a"
        gap = stats.last_rotation_gap_ms
        print(
            f"forced rotation every {rotate}s: rotations={stats.rotations} "
            f"duplicates_dropped={stats.duplicates_dropped} lost_sentences={lost} "
            f"last_rotation_gap_ms={gap}"
        )
        after: list[int] = []
        for _number, t_audio in rotation_marks:
            index = max(
                (i for i, b in enumerate(boundaries) if b["start_ms"] <= t_audio), default=None
            )
            if index is not None and index < len(first):
                after.append(first[index])
        if after:
            print(f"first partial of the sentence after each rotation (ms): {after}")
    vad = f"{settings.vad_mode.value} ({settings.vad_silence_ms} ms, rms {settings.vad_threshold})"
    print(f"vad: {vad}")
    print(f"WER vs reference: {wer:.1%}" if reference else "WER: no reference transcript")
    if boundaries:
        print(f"first partial after sentence start p50/p95: {fmt_p(first)} ms")
        print(f"utterance-to-final p50/p95: {fmt_p(utt)} ms ({len(utt)} sentences)")
    else:
        print("speech-to-caption latency: no sentence boundaries (.json) next to the sample")
    print(f"commit delay (last partial -> final) p50/p95: {fmt_p(final_lat)} ms")
    print(f"tokens: prompt={stats.prompt_tokens} response={stats.response_tokens}")
    estimated = " (estimated: no usage_metadata received)" if not stats.response_tokens else ""
    print(f"audio: {audio_seconds:.1f} s  estimated cost: ${cost:.4f}{estimated}")
    append_metrics_row(
        sample=sample,
        mode=f"{settings.stt_mode.value} · glossary={glossary_label}",
        finals=len(finals),
        wer=wer,
        first=first,
        utt=utt,
        final_lat=final_lat,
        prompt_tokens=stats.prompt_tokens,
        response_tokens=stats.response_tokens,
        cost=cost,
    )
    ok = len(finals) > 0 and (not reference or wer <= WER_LIMIT)
    print("RESULT:", "PASS" if ok else f"FAIL (need >= 1 final and WER <= {WER_LIMIT:.0%})")
    return 0 if ok else 1


def append_metrics_row(
    *,
    sample: Path,
    mode: str,
    finals: int,
    wer: float,
    first: list[int],
    utt: list[int],
    final_lat: list[int],
    prompt_tokens: int,
    response_tokens: int,
    cost: float,
) -> None:
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not METRICS_FILE.is_file():
        METRICS_FILE.write_text(METRICS_INTRO + METRICS_HEADER, encoding="utf-8")
    stamp = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M")
    row = (
        f"| {stamp} | {sample.name} | {mode} | {finals} | {wer:.1%} | {fmt_p(first)} | "
        f"{fmt_p(utt)} | {fmt_p(final_lat)} | {prompt_tokens}/{response_tokens} | "
        f"{cost:.4f} |\n"
    )
    lines = METRICS_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
    header = METRICS_HEADER.splitlines()[0].strip()
    insert_at = len(lines)
    for index, line in enumerate(lines):
        if line.strip() == header:
            insert_at = index + 1
            while insert_at < len(lines) and lines[insert_at].startswith("|"):
                insert_at += 1
            break
    lines.insert(insert_at, row)
    METRICS_FILE.write_text("".join(lines), encoding="utf-8")


async def apply_glossary_option(
    stage: StageConfig, option: str, settings: Settings
) -> tuple[StageConfig, str]:
    """none → empty list; manual → stages.yaml list; auto → manual + Diccionario suggestions."""
    if option == "none":
        return stage.model_copy(update={"glossary": []}), "none"
    if option == "auto":
        terms = await GeminiAutoGlossary(settings).suggest(stage)
        merged = merge_glossary(stage.glossary, terms)
        added = len(merged) - len(stage.glossary)
        return stage.model_copy(update={"glossary": merged}), f"auto (+{added})"
    return stage, f"manual ({len(stage.glossary)})"


def pick_stage(sample: Path, stage_id: str | None) -> StageConfig:
    stages_path = Path("stages.yaml")
    if stages_path.is_file():
        stages = StagesFile.load(stages_path)
        if stage_id:
            stage = stages.by_id(stage_id)
        else:
            stage = next((s for s in stages.stages if Path(s.source).name == sample.name), None)
        if stage is not None:
            return stage
    return StageConfig(id="smoke", name="Smoke", source=str(sample))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lenguaraz smoke-stt")
    parser.add_argument("--sample", default="samples/en_kubernetes.wav")
    parser.add_argument("--stage", default=None, help="stage id from stages.yaml")
    parser.add_argument("--mode", choices=["SMART", "VERBATIM"], default=None)
    parser.add_argument("--verbose", action="store_true", help="print every partial")
    parser.add_argument(
        "--rotate", type=int, default=None, help="force a session rotation every N seconds"
    )
    parser.add_argument(
        "--glossary",
        choices=["manual", "none", "auto"],
        default="manual",
        help="custom_vocabulary: the stage list (manual), nothing, or manual + auto-glossary",
    )
    args = parser.parse_args(argv)
    sample = Path(args.sample)
    if not sample.is_file():
        print(f"sample not found: {sample}", file=sys.stderr)
        return 2
    try:
        return asyncio.run(
            run(
                sample,
                pick_stage(sample, args.stage),
                args.mode,
                args.verbose,
                args.rotate,
                args.glossary,
            )
        )
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
