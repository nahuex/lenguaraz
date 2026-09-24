# SPDX-License-Identifier: Apache-2.0
"""``make smoke-translate``: translate sample segments with the real model, in both directions.

Uses quota. For each segment it measures time to first token and total time, records token
usage, and checks glossary adherence: every glossary term that appears in the source must
appear verbatim in the translation (spec 002 NFR-002-04). Appends a row to ``docs/metrics.md``.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from lenguaraz.config import ConfigError, EngineKind, StageConfig, StagesFile, load_settings
from lenguaraz.metrics import percentile
from lenguaraz.translate.base import TranslationRequest, TranslationUsage
from lenguaraz.translate.gemini import GeminiTranslationEngine

METRICS_FILE = Path("docs/metrics.md")
SECTION = "## smoke-translate runs"
HEADER = (
    "| Date (UTC) | Direction | Segments | TTFT p50/p95 ms | Total p50/p95 ms | "
    "Glossary adherence | Tokens (in/out) | Est. cost USD |\n"
    "|---|---|---|---|---|---|---|---|\n"
)
PRICE_IN_PER_M = 0.30  # gemini-3.5-flash-lite, GT-6.3 (2026-09-22)
PRICE_OUT_PER_M = 2.50
ADHERENCE_LIMIT = 0.95


@dataclass(slots=True)
class Run:
    direction: str
    ttft: list[int]
    total: list[int]
    hits: int = 0
    checks: int = 0
    usage: TranslationUsage | None = None
    outputs: list[tuple[str, str]] | None = None


def read_sentences(path: Path, limit: int) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
    return kept[:limit]


def glossary_adherence(source: str, translation: str, glossary: Sequence[str]) -> tuple[int, int]:
    hits = checks = 0
    low_source = source.lower()
    for term in glossary:
        if term.lower() in low_source:
            checks += 1
            if term in translation or term.lower() in translation.lower():
                hits += 1
    return hits, checks


def fmt_p(values: list[int]) -> str:
    return f"{percentile(values, 50)}/{percentile(values, 95)}" if values else "n/a"


async def translate_set(
    engine: GeminiTranslationEngine,
    stage: StageConfig,
    sentences: Sequence[str],
    source_lang: str,
    target_lang: str,
) -> Run:
    run = Run(direction=f"{source_lang}→{target_lang}", ttft=[], total=[], outputs=[])
    usage = TranslationUsage()
    context: list[tuple[str, str]] = []
    for text in sentences:
        request = TranslationRequest(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
            glossary=tuple(stage.glossary),
            context=tuple(context[-3:]),
            talk_title=stage.talk.title,
            talk_abstract=stage.talk.abstract,
        )
        started = time.monotonic()
        first: list[float] = []

        def on_delta(_chunk: str, first: list[float] = first) -> None:
            if not first:
                first.append(time.monotonic())

        outcome = await engine.translate(request, on_delta=on_delta)
        finished = time.monotonic()
        run.total.append(round((finished - started) * 1000))
        if first:
            run.ttft.append(round((first[0] - started) * 1000))
        hits, checks = glossary_adherence(text, outcome.text, stage.glossary)
        run.hits += hits
        run.checks += checks
        usage.add(outcome.usage)
        context.append((text, outcome.text))
        assert run.outputs is not None
        run.outputs.append((text, outcome.text))
        ttft = str(run.ttft[-1]) if first else "-"
        print(f"[{run.direction} {run.total[-1]:5d} ms, ttft {ttft:>4}] {outcome.text}")
    run.usage = usage
    return run


def cost(usage: TranslationUsage) -> float:
    return usage.input_tokens / 1e6 * PRICE_IN_PER_M + usage.output_tokens / 1e6 * PRICE_OUT_PER_M


def append_row(run: Run) -> None:
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    text = METRICS_FILE.read_text(encoding="utf-8") if METRICS_FILE.is_file() else "# Metrics\n"
    if SECTION not in text:
        text = text.rstrip() + "\n\n" + SECTION + "\n\n" + HEADER
    usage = run.usage or TranslationUsage()
    adherence = f"{run.hits}/{run.checks}" + (
        f" ({run.hits / run.checks:.0%})" if run.checks else ""
    )
    stamp = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M")
    row = (
        f"| {stamp} | {run.direction} | {len(run.total)} | "
        f"{fmt_p(run.ttft)} | {fmt_p(run.total)} | {adherence} | "
        f"{usage.input_tokens}/{usage.output_tokens} | {cost(usage):.4f} |\n"
    )
    head, _, tail = text.partition(SECTION)
    tail_lines = tail.split("\n")
    # append after the last table row of the section
    insert_at = len(tail_lines)
    for index in range(len(tail_lines) - 1, -1, -1):
        if tail_lines[index].startswith("|"):
            insert_at = index + 1
            break
    tail_lines.insert(insert_at, row.rstrip("\n"))
    METRICS_FILE.write_text(head + SECTION + "\n".join(tail_lines), encoding="utf-8")


async def run_all(en_limit: int, es_limit: int) -> int:
    settings = load_settings()
    if settings.engine is not EngineKind.GEMINI:
        raise ConfigError("smoke-translate needs ENGINE=gemini and a GEMINI_API_KEY in .env")
    stages = StagesFile.load(settings.stages_file)
    engine = GeminiTranslationEngine(settings)
    runs: list[Run] = []
    plan = [
        ("main", "samples/en_kubernetes.txt", "en-US", "es", en_limit),
        ("workshop", "samples/es_asyncio.txt", "es-419", "en", es_limit),
    ]
    for stage_id, script, source_lang, target_lang, limit in plan:
        stage = stages.by_id(stage_id) or StageConfig(id=stage_id, name=stage_id, source=script)
        sentences = read_sentences(Path(script), limit)
        if not sentences:
            continue
        model = settings.gemini_translate_model
        print(f"\n=== {source_lang} -> {target_lang} ({len(sentences)} segments, {model}) ===")
        runs.append(await translate_set(engine, stage, sentences, source_lang, target_lang))

    ok = True
    print("\n=== smoke-translate summary ===")
    for run in runs:
        usage = run.usage or TranslationUsage()
        adherence = run.hits / run.checks if run.checks else 1.0
        print(f"{run.direction}: {len(run.total)} segments | TTFT p50/p95 {fmt_p(run.ttft)} ms")
        glossary = f"{run.hits}/{run.checks} ({adherence:.0%})"
        print(f"  total p50/p95 {fmt_p(run.total)} ms | glossary {glossary}")
        print(f"  tokens {usage.input_tokens}/{usage.output_tokens} | est. ${cost(usage):.4f}")
        append_row(run)
        if adherence < ADHERENCE_LIMIT or len(run.total) == 0:
            ok = False
    print("RESULT:", "PASS" if ok else f"FAIL (glossary adherence < {ADHERENCE_LIMIT:.0%})")
    return 0 if ok else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lenguaraz smoke-translate")
    parser.add_argument("--en", type=int, default=5, help="EN→ES segments from the EN sample")
    parser.add_argument("--es", type=int, default=3, help="ES→EN segments from the ES sample")
    args = parser.parse_args(argv)
    try:
        return asyncio.run(run_all(args.en, args.es))
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
