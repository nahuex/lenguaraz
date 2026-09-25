# SPDX-License-Identifier: Apache-2.0
"""``make simulate``: run N stages in one process and write a scale report (spec 005).

Any mix of real Gemini stages (``--real K``) and fake ones; the report states which is which
(Constitution Art. XIV). CPU and memory come from ``psutil`` when installed.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import platform
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from lenguaraz.bus.memory import MemoryBus
from lenguaraz.config import EngineKind, Settings, StageConfig, StagesFile, load_settings
from lenguaraz.metrics import percentile
from lenguaraz.models import CaptionEvent
from lenguaraz.pricing import PRICING_DATE
from lenguaraz.runner import StageManager
from lenguaraz.stt.base import SttEngine, SttSession
from lenguaraz.stt.fake import FakeSttEngine
from lenguaraz.translate.base import (
    DeltaCallback,
    TranslationEngine,
    TranslationOutcome,
    TranslationRequest,
)
from lenguaraz.translate.fake import FakeTranslator

SAMPLES = (
    ("samples/en_kubernetes.wav", ["en-US"], ["es"]),
    ("samples/es_asyncio.wav", ["es-419"], ["en"]),
)
REPORT_MD = Path("docs/scale-report.md")
REPORT_JSON = Path("docs/scale-report.json")


class MixedSttEngine:
    name = "mixed"

    def __init__(self, real: SttEngine | None, fake: SttEngine, real_ids: set[str]) -> None:
        self._real = real
        self._fake = fake
        self._real_ids = real_ids

    async def open(self, stage: StageConfig) -> SttSession:
        if self._real is not None and stage.id in self._real_ids:
            return await self._real.open(stage)
        return await self._fake.open(stage)


class MixedTranslationEngine:
    name = "mixed"

    def __init__(
        self, real: TranslationEngine | None, fake: TranslationEngine, real_ids: set[str]
    ) -> None:
        self._real = real
        self._fake = fake
        self._real_ids = real_ids

    async def translate(
        self, request: TranslationRequest, on_delta: DeltaCallback | None = None
    ) -> TranslationOutcome:
        # The fan-out does not pass the stage id; the last glossary term carries it.
        marker = request.glossary[-1] if request.glossary else ""
        if self._real is not None and marker in self._real_ids:
            return await self._real.translate(request, on_delta)
        return await self._fake.translate(request, on_delta)


@dataclass(slots=True)
class StageResult:
    id: str
    real: bool
    finals: int = 0
    interims: int = 0
    translated: int = 0
    commit_delay_ms: list[int] = field(default_factory=list)
    translation_ms: list[int] = field(default_factory=list)
    final_state: str = ""
    errors: int = 0
    rotations: int = 0
    est_cost_usd: float = 0.0
    audio_seconds: float = 0.0


@dataclass(slots=True)
class Report:
    stages: int
    real: int
    seconds: float
    machine: str
    cpu_avg_percent: float | None
    cpu_max_percent: float | None
    rss_start_mb: float | None
    rss_end_mb: float | None
    finals_total: int
    interims_total: int
    translated_total: int
    real_commit_delay_p50_p95: tuple[int, int] | None
    real_translation_p50_p95: tuple[int, int] | None
    fake_commit_delay_p50_p95: tuple[int, int] | None
    real_cost_usd: float
    cost_per_stage_hour_usd: float | None
    pricing_date: str
    per_stage: list[dict[str, Any]]
    honesty: str


def build_stages(count: int) -> StagesFile:
    stages = []
    for index in range(count):
        source, source_lang, targets = SAMPLES[index % len(SAMPLES)]
        stage_id = f"sim-{index + 1:02d}"
        stages.append(
            StageConfig(
                id=stage_id,
                name=f"Simulated stage {index + 1}",
                source=source,
                source_lang=source_lang,
                targets=targets,
                glossary=["Kubernetes", "eBPF", stage_id],  # stage id as a routing marker
                loop=True,
            )
        )
    return StagesFile(stages=stages)


def _p50_p95(values: list[int]) -> tuple[int, int] | None:
    return (percentile(values, 50), percentile(values, 95)) if values else None


async def simulate(
    *,
    stages: int,
    seconds: float,
    real: int,
    settings: Settings | None = None,
    fake_words_per_second: float = 2.5,
) -> Report:
    settings = settings or load_settings(engine=EngineKind.FAKE)
    real = max(0, min(real, stages))
    real_ids = {f"sim-{i + 1:02d}" for i in range(real)}
    real_stt: SttEngine | None = None
    real_tr: TranslationEngine | None = None
    if real:
        from lenguaraz.engines import build_stt_engine, build_translation_engine

        gemini_settings = load_settings(engine=EngineKind.GEMINI)
        real_stt = build_stt_engine(gemini_settings)
        real_tr = build_translation_engine(gemini_settings)
    stt = MixedSttEngine(real_stt, FakeSttEngine(words_per_second=fake_words_per_second), real_ids)
    translator = MixedTranslationEngine(real_tr, FakeTranslator(), real_ids)

    bus = MemoryBus(queue_size=2000)
    stages_file = build_stages(stages)
    manager = StageManager(
        stages_file,
        engine=stt,
        bus=bus,
        settings=settings,
        translator=translator,
        metrics_interval=1.0,
    )
    results = {s.id: StageResult(id=s.id, real=s.id in real_ids) for s in stages_file.stages}

    async def listen(stage: StageConfig, lang: str) -> None:
        sub = bus.subscribe(stage.id, lang)
        result = results[stage.id]
        source = stage.primary_source_lang
        try:
            async for event in sub:
                if not isinstance(event, CaptionEvent):
                    continue
                if event.lang == source:
                    if event.is_final:
                        result.finals += 1
                        result.commit_delay_ms.append(event.latency_ms)
                    else:
                        result.interims += 1
                elif event.is_final:
                    result.translated += 1
                    result.translation_ms.append(event.latency_ms)
        finally:
            sub.close()

    listeners = [
        asyncio.create_task(listen(stage, lang))
        for stage in stages_file.stages
        for lang in stage.languages()[:2]
    ]

    process: Any = None
    cpu_samples: list[float] = []
    rss_start = rss_end = None
    with contextlib.suppress(Exception):  # psutil is optional
        import psutil

        process = psutil.Process(os.getpid())
        process.cpu_percent(None)
        rss_start = process.memory_info().rss / 1e6

    await manager.start_all()
    started = time.monotonic()
    while time.monotonic() - started < seconds:
        await asyncio.sleep(1.0)
        if process is not None:
            cpu_samples.append(process.cpu_percent(None))
    if process is not None:
        rss_end = process.memory_info().rss / 1e6
    snapshots = {row["id"]: row for row in manager.snapshot()}
    await manager.stop_all()
    for task in listeners:
        task.cancel()
    for task in listeners:
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task

    for stage_id, result in results.items():
        row = snapshots.get(stage_id, {})
        result.final_state = row.get("state", "")
        result.errors = int(row.get("errors", 0))
        result.rotations = int(row.get("rotations", 0))
        result.est_cost_usd = float(row.get("est_cost_usd", 0.0)) if result.real else 0.0
        result.audio_seconds = float(row.get("audio_seconds", 0.0))

    real_results = [r for r in results.values() if r.real]
    fake_results = [r for r in results.values() if not r.real]
    real_cost = sum(r.est_cost_usd for r in real_results)
    per_hour = (real_cost / (real * seconds) * 3600) if real and seconds else None
    elapsed = time.monotonic() - started
    machine = (
        f"{platform.system()} {platform.machine()}, {os.cpu_count() or 1} CPUs, "
        f"Python {platform.python_version()}"
    )
    return Report(
        stages=stages,
        real=real,
        seconds=round(elapsed, 1),
        machine=machine,
        cpu_avg_percent=round(sum(cpu_samples) / len(cpu_samples), 1) if cpu_samples else None,
        cpu_max_percent=round(max(cpu_samples), 1) if cpu_samples else None,
        rss_start_mb=round(rss_start, 1) if rss_start is not None else None,
        rss_end_mb=round(rss_end, 1) if rss_end is not None else None,
        finals_total=sum(r.finals for r in results.values()),
        interims_total=sum(r.interims for r in results.values()),
        translated_total=sum(r.translated for r in results.values()),
        real_commit_delay_p50_p95=_p50_p95([v for r in real_results for v in r.commit_delay_ms]),
        real_translation_p50_p95=_p50_p95([v for r in real_results for v in r.translation_ms]),
        fake_commit_delay_p50_p95=_p50_p95([v for r in fake_results for v in r.commit_delay_ms]),
        real_cost_usd=round(real_cost, 4),
        cost_per_stage_hour_usd=round(per_hour, 4) if per_hour is not None else None,
        pricing_date=PRICING_DATE,
        per_stage=[
            {
                "id": r.id,
                "real": r.real,
                "state": r.final_state,
                "finals": r.finals,
                "interims": r.interims,
                "translated": r.translated,
                "commit_delay_p50_ms": percentile(r.commit_delay_ms, 50),
                "commit_delay_p95_ms": percentile(r.commit_delay_ms, 95),
                "translation_p50_ms": percentile(r.translation_ms, 50),
                "errors": r.errors,
                "rotations": r.rotations,
                "audio_seconds": r.audio_seconds,
                "est_cost_usd": r.est_cost_usd,
            }
            for r in results.values()
        ],
        honesty=(
            f"{real} real Gemini stage(s) and {stages - real} simulated stage(s) "
            "(fake engines replaying the bundled samples) ran in one process for "
            f"{elapsed:.0f} s; CPU/RSS cover the whole process; cost covers the real stages only."
        ),
    )


def write_report(report: Report, out_md: Path = REPORT_MD, out_json: Path = REPORT_JSON) -> None:
    """Write the report; a ``## Viewer fan-out`` section left by ``make loadtest`` survives."""
    from lenguaraz.tools.loadtest import FANOUT_HEADING, extract_section, upsert_section

    out_md.parent.mkdir(parents=True, exist_ok=True)
    markdown = render_markdown(report)
    if out_md.is_file():
        fanout = extract_section(out_md.read_text(encoding="utf-8"), FANOUT_HEADING)
        if fanout:
            markdown = upsert_section(markdown, FANOUT_HEADING, fanout)
    out_md.write_text(markdown, encoding="utf-8")
    out_json.write_text(json.dumps(asdict(report), indent=2) + "\n", encoding="utf-8")


def _pp(value: tuple[int, int] | None) -> str:
    return f"{value[0]} / {value[1]}" if value else "n/a"


def render_markdown(report: Report) -> str:
    summary = [
        (
            "Stages (real / simulated)",
            f"{report.stages} ({report.real} / {report.stages - report.real})",
        ),
        ("Duration", f"{report.seconds} s"),
        ("Machine", report.machine),
        (
            "CPU of the process (avg / max, % of one core)",
            f"{report.cpu_avg_percent} / {report.cpu_max_percent}",
        ),
        ("RSS (start -> end, MB)", f"{report.rss_start_mb} -> {report.rss_end_mb}"),
        (
            "Finals / partials / translated captions",
            f"{report.finals_total} / {report.interims_total} / {report.translated_total}",
        ),
        ("Real stages: commit delay p50 / p95 (ms)", _pp(report.real_commit_delay_p50_p95)),
        ("Real stages: translation latency p50 / p95 (ms)", _pp(report.real_translation_p50_p95)),
        ("Simulated stages: commit delay p50 / p95 (ms)", _pp(report.fake_commit_delay_p50_p95)),
        ("Measured cost of the real stages (USD)", str(report.real_cost_usd)),
        (
            f"Cost per stage-hour (USD, pricing {report.pricing_date})",
            str(report.cost_per_stage_hour_usd),
        ),
    ]
    lines = [
        "# Scale report",
        "",
        f"Generated by `make simulate` (spec 005). {report.honesty}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    lines += [f"| {name} | {value} |" for name, value in summary]
    columns = [
        "Stage",
        "Real",
        "State",
        "Finals",
        "Partials",
        "Translated",
        "Commit p50/p95 ms",
        "Translation p50 ms",
        "Errors",
        "Rotations",
        "Audio s",
        "Cost USD",
    ]
    lines += [
        "",
        "## Per stage",
        "",
        "| " + " | ".join(columns) + " |",
        "|" + "---|" * len(columns),
    ]
    for row in report.per_stage:
        cells = [
            row["id"],
            "yes" if row["real"] else "no",
            row["state"],
            row["finals"],
            row["interims"],
            row["translated"],
            f"{row['commit_delay_p50_ms']}/{row['commit_delay_p95_ms']}",
            row["translation_p50_ms"],
            row["errors"],
            row["rotations"],
            row["audio_seconds"],
            row["est_cost_usd"],
        ]
        lines.append("| " + " | ".join(str(c) for c in cells) + " |")
    lines += [
        "",
        "## Method",
        "",
        "- Every stage is an independent pipeline (ingest, STT, bus, translation fan-out) in one",
        "  process, with one listener per language subscribed like a browser would be.",
        "- Commit delay = time between the last partial and the final caption (`latency_ms`);",
        "  0 when the server sent a final without partials.",
        "- Translation latency = time from the final caption to its translation being published.",
        "- Cost = measured audio seconds x 25 tokens/s at the STT price + measured translation",
        f"  tokens, prices read on {report.pricing_date}; simulated stages cost nothing and are",
        "  excluded.",
        "",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lenguaraz simulate")
    parser.add_argument("--stages", type=int, default=10)
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--real", type=int, default=2, help="stages on the real Gemini engines")
    parser.add_argument("--out", default=str(REPORT_MD))
    args = parser.parse_args(argv)
    out_md = Path(args.out)
    report = asyncio.run(simulate(stages=args.stages, seconds=args.seconds, real=args.real))
    write_report(report, out_md, out_md.with_suffix(".json"))
    print(render_markdown(report))
    print(f"written: {out_md} and {out_md.with_suffix('.json')}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
