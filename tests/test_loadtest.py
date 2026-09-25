# SPDX-License-Identifier: Apache-2.0
"""Spec 005 follow-up — FR-005-05 / AC-4: the viewer fan-out load test (fake engine)."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from lenguaraz.tools import simulate
from lenguaraz.tools.loadtest import (
    FANOUT_HEADING,
    Report,
    StepResult,
    compute_spread,
    extract_section,
    parse_args,
    parse_viewers,
    render_markdown,
    run_loadtest,
    scale_report_section,
    upsert_section,
    write_report,
)

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_TIMEOUT_SECONDS = 150.0


def test_spread_uses_complete_events_and_reports_coverage() -> None:
    receipts = {
        ("main", "en", 1, False, "a"): [10.000, 10.010, 10.005],  # 10 ms, every viewer
        ("main", "en", 1, True, "a b."): [10.100, 10.150, 10.120],  # 50 ms, every viewer
        ("main", "en", 2, False, "x"): [10.200, 10.900],  # one viewer missed it: excluded
        ("main", "en", 2, True, "x y."): [10.300],  # a single receipt has no spread
    }
    stats = compute_spread(receipts, connected=3)
    assert stats.events == 4 and stats.complete == 2 and stats.basis == "complete"
    assert (stats.p50_ms, stats.p95_ms, stats.max_ms) == (10, 50, 50)
    assert stats.coverage_median == pytest.approx(0.833, abs=0.001)


def test_spread_counts_completeness_per_stage_and_language() -> None:
    receipts = {
        ("main", "en", 1, True, "a."): [0.000, 0.004, 0.008],  # all 3 main viewers: 8 ms
        ("workshop", "es", 1, True, "b."): [0.000, 0.020],  # both workshop viewers: 20 ms
        ("workshop", "es", 2, True, "c."): [0.000],  # one of two: incomplete
    }
    stats = compute_spread(receipts, {("main", "en"): 3, ("workshop", "es"): 2})
    assert stats.complete == 2 and stats.basis == "complete"
    assert (stats.p50_ms, stats.p95_ms, stats.max_ms) == (8, 20, 20)
    assert stats.coverage_median == 1.0
    assert compute_spread(receipts, 5).complete == 0  # a global count would hide completeness


def test_spread_falls_back_to_partial_events_and_handles_nothing() -> None:
    partial = compute_spread({("s", "en", 1, True, "t"): [0.0, 0.7]}, connected=5)
    assert partial.basis == "partial" and partial.complete == 0 and partial.p95_ms == 700
    empty = compute_spread({}, connected=0)
    assert (empty.events, empty.p50_ms, empty.p95_ms, empty.max_ms) == (0, 0, 0, 0)
    assert empty.coverage_median == 0.0


def test_argument_parsing_defaults_and_viewer_steps() -> None:
    args = parse_args([])
    assert args.viewers == [100, 500, 1000] and args.seconds == 30.0 and args.stages == 1
    assert args.out == "docs/loadtest-report.md" and args.scale_report == "docs/scale-report.md"
    custom = parse_args(["--viewers", "20, 40", "--seconds", "2", "--stages", "2", "--port", "1"])
    assert custom.viewers == [20, 40] and custom.seconds == 2.0 and custom.port == 1
    assert parse_viewers("750") == [750]
    for bad in ("0", "abc", "10,-5", ""):
        with pytest.raises(SystemExit):
            parse_args(["--viewers", bad])


def _report(**overrides: object) -> Report:
    step = StepResult(
        viewers=20,
        stages=1,
        connected=19,
        failed=1,
        disconnected=0,
        connect_seconds=0.4,
        hold_seconds=2.0,
        close_seconds=0.1,
        events_total=6,
        events_complete=5,
        spread_basis="complete",
        coverage_median=1.0,
        events_per_client_min=5,
        events_per_client_median=6,
        caption_msgs_per_second=57.0,
        spread_p50_ms=3,
        spread_p95_ms=9,
        spread_max_ms=11,
        server_cpu_avg_percent=4.2,
        server_cpu_max_percent=9.0,
        server_rss_start_mb=60.0,
        server_rss_end_mb=62.5,
        server_rss_delta_mb=2.5,
        client_cpu_avg_percent=None,
        client_cpu_max_percent=None,
        failures={"ConnectionRefusedError": 1},
    )
    fields: dict[str, object] = {
        "generated_at": "2026-09-25 02:00 UTC",
        "machine": "TestOS x86, 4 CPUs, Python 3.12",
        "engine": "fake",
        "stage_ids": ["main"],
        "seconds": 2.0,
        "steps": [step],
        "honesty": "Fake engine; same host; loopback.",
    }
    fields.update(overrides)
    return Report(**fields)  # type: ignore[arg-type]


def test_render_markdown_has_the_table_the_failures_and_the_honesty_note() -> None:
    markdown = render_markdown(_report())
    assert markdown.startswith("# Viewer fan-out load test")
    assert "| 20 on 1 stage(s) | 19 / 1 / 0 | 5 / 6 | 3 / 9 / 11 | 5 of 6 (complete) |" in markdown
    assert "| 4.2 / 9.0 | 60.0 -> 62.5 (2.5) | n/a / n/a | 57.0 |" in markdown
    assert "- 20 viewers: 1 x `ConnectionRefusedError`" in markdown
    assert "Fake engine; same host; loopback." in markdown and "## Method" in markdown
    section = scale_report_section(_report(), "loadtest-report.md")
    assert "| 20 | 19 | 3 / 9 | 4.2 / 9.0 | 2.5 |" in section
    assert "[`loadtest-report.md`](loadtest-report.md)" in section


def test_upsert_section_appends_then_replaces_in_place() -> None:
    doc = "# Scale report\n\n## Summary\n\n| a | b |\n\n## Method\n\n- one\n"
    once = upsert_section(doc, FANOUT_HEADING, "first body")
    assert once.endswith("## Method\n\n- one\n\n## Viewer fan-out\n\nfirst body\n")
    twice = upsert_section(once, FANOUT_HEADING, "second body")
    assert twice.count(FANOUT_HEADING) == 1 and "first body" not in twice
    assert extract_section(twice, FANOUT_HEADING) == "second body"
    middle = upsert_section(
        "## A\n\na\n\n## Viewer fan-out\n\nold\n\n## Z\n\nz\n", FANOUT_HEADING, "new"
    )
    assert middle == "## A\n\na\n\n## Viewer fan-out\n\nnew\n\n## Z\n\nz\n"
    assert extract_section(doc, FANOUT_HEADING) is None
    assert upsert_section("", FANOUT_HEADING, "body") == "## Viewer fan-out\n\nbody\n"


def test_simulate_report_keeps_the_viewer_fanout_section(tmp_path: Path) -> None:
    out_md = tmp_path / "scale-report.md"
    out_md.write_text("# Scale report\n\n## Viewer fan-out\n\nmeasured numbers\n", encoding="utf-8")
    report = simulate.Report(
        stages=1,
        real=0,
        seconds=1.0,
        machine="m",
        cpu_avg_percent=None,
        cpu_max_percent=None,
        rss_start_mb=None,
        rss_end_mb=None,
        finals_total=0,
        interims_total=0,
        translated_total=0,
        real_commit_delay_p50_p95=None,
        real_translation_p50_p95=None,
        fake_commit_delay_p50_p95=None,
        real_cost_usd=0.0,
        cost_per_stage_hour_usd=None,
        pricing_date="2026-09-22",
        per_stage=[],
        honesty="h",
    )
    simulate.write_report(report, out_md, tmp_path / "scale-report.json")
    text = out_md.read_text(encoding="utf-8")
    assert text.startswith("# Scale report") and "## Method" in text
    assert extract_section(text, FANOUT_HEADING) == "measured numbers"


def test_twenty_viewers_against_a_fake_engine_server(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Integration: real subprocess server, 20 sockets, 2 s window; bounded by a join timeout."""
    monkeypatch.chdir(ROOT)  # stages.yaml and the samples are relative to the repo root
    outcome: dict[str, object] = {}

    def worker() -> None:
        try:
            outcome["report"] = run_loadtest(
                viewers=[20], seconds=2.0, stages=1, stages_file=ROOT / "stages.yaml"
            )
        except BaseException as exc:  # surfaced by the assertion below
            outcome["error"] = exc

    thread = threading.Thread(target=worker, name="loadtest-integration", daemon=True)
    thread.start()
    thread.join(INTEGRATION_TIMEOUT_SECONDS)
    assert not thread.is_alive(), f"load test still running after {INTEGRATION_TIMEOUT_SECONDS}s"
    assert "error" not in outcome, outcome.get("error")
    report = outcome["report"]
    assert isinstance(report, Report)
    assert report.engine == "fake" and report.stage_ids == ["main"] and len(report.steps) == 1
    step = report.steps[0]
    assert step.connected == 20 and step.failed == 0 and step.disconnected == 0
    assert step.events_per_client_min >= 1 and step.events_total >= 1
    assert step.events_complete >= 1 and step.spread_basis == "complete"
    assert 0 <= step.spread_p50_ms <= step.spread_p95_ms <= step.spread_max_ms
    assert 1.9 <= step.hold_seconds <= 4.0
    if step.server_rss_end_mb is not None:  # psutil present: the sampled process is the server,
        assert step.server_rss_end_mb > 30  # not a 14 MB launcher stub (Windows venv python.exe)

    out_md = tmp_path / "loadtest-report.md"
    write_report(report, out_md, tmp_path / "loadtest-report.json")
    markdown = out_md.read_text(encoding="utf-8")
    assert markdown.startswith("# Viewer fan-out load test") and "| 20 on 1 stage(s) |" in markdown
    data = json.loads((tmp_path / "loadtest-report.json").read_text(encoding="utf-8"))
    assert data["steps"][0]["connected"] == 20 and data["engine"] == "fake"
