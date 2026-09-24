# SPDX-License-Identifier: Apache-2.0
"""Spec 001 — FR-001-13, AC-14 (latency window, p50/p95)."""

from __future__ import annotations

from lenguaraz.metrics import LatencyWindow, StageMetrics, percentile


def test_percentile_nearest_rank() -> None:
    values = list(range(100, 1100, 100))  # 100..1000
    assert percentile(values, 50) == 500
    assert percentile(values, 95) == 1000
    assert percentile([42], 95) == 42
    assert percentile([], 50) == 0


def test_window_is_bounded() -> None:
    window = LatencyWindow(size=3)
    for value in (1000, 2000, 3000, 10):
        window.add(value)
    assert len(window) == 3
    assert window.p50 == 2000
    assert window.p95 == 3000


def test_stage_metrics_separate_interims_from_finals() -> None:
    metrics = StageMetrics()
    metrics.record(300, is_final=False)
    metrics.record(900, is_final=True)
    metrics.record(1100, is_final=True)
    assert metrics.captions_interim == 1
    assert metrics.captions_final == 2
    assert metrics.finals.p50 == 900
    assert metrics.interims.p95 == 300
