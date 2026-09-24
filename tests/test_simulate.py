# SPDX-License-Identifier: Apache-2.0
"""Spec 005 — AC-1: the simulator runs fake stages without credentials and writes a report."""

from __future__ import annotations

import json
from pathlib import Path

from lenguaraz.config import Settings
from lenguaraz.tools.simulate import build_stages, render_markdown, simulate, write_report

ROOT = Path(__file__).resolve().parents[1]


def test_build_stages_alternates_samples_and_marks_routing() -> None:
    stages = build_stages(3)
    assert [s.id for s in stages.stages] == ["sim-01", "sim-02", "sim-03"]
    assert stages.stages[0].source_lang == ["en-US"] and stages.stages[1].source_lang == ["es-419"]
    assert stages.stages[2].glossary[-1] == "sim-03" and stages.stages[2].loop is True


async def test_fake_only_simulation_writes_an_honest_report(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(ROOT)
    out_md = tmp_path / "scale-report.md"
    report = await simulate(
        stages=5,
        seconds=2.0,
        real=0,
        settings=Settings(_env_file=None, engine="fake", always_on_langs="es,en"),
        fake_words_per_second=12,
    )
    write_report(report, out_md, tmp_path / "scale-report.json")
    assert report.stages == 5 and report.real == 0
    assert report.finals_total > 0 and report.translated_total > 0
    assert all(row["finals"] > 0 for row in report.per_stage)
    assert report.fake_commit_delay_p50_p95 is not None
    assert report.real_commit_delay_p50_p95 is None and report.cost_per_stage_hour_usd is None
    assert "0 real Gemini stage(s) and 5 simulated" in report.honesty
    markdown = out_md.read_text(encoding="utf-8")
    assert markdown.startswith("# Scale report") and "| sim-05 |" in markdown
    data = json.loads((tmp_path / "scale-report.json").read_text(encoding="utf-8"))
    assert data["stages"] == 5 and len(data["per_stage"]) == 5
    assert render_markdown(report) == markdown
