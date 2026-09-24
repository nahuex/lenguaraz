# SPDX-License-Identifier: Apache-2.0
"""Spec 002 — FR-002-04, AC-2, NFR-002-05: language demand."""

from __future__ import annotations

from lenguaraz.translate.demand import LanguageDemand


def test_always_on_and_listeners_with_grace() -> None:
    now = [1000.0]
    demand = LanguageDemand(["es"], grace_seconds=10, clock=lambda: now[0])
    targets = ["es", "pt"]
    assert demand.active(targets) == ["es"]

    demand.observe(["pt"])  # first listener on pt
    assert demand.active(targets) == ["es", "pt"]

    now[0] += 5.0  # listener gone for 5 s: still within grace
    assert demand.active(targets) == ["es", "pt"]

    now[0] += 5.1  # grace elapsed
    assert demand.active(targets) == ["es"]

    demand.observe(["pt"])
    now[0] += 11.0
    demand.observe(["pt"])  # seen again → stays
    assert demand.active(targets) == ["es", "pt"]


def test_only_configured_targets_and_no_duplicates() -> None:
    demand = LanguageDemand(["es", "ES", "fr"], grace_seconds=10, clock=lambda: 0.0)
    demand.observe(["en", "de", "ES"])
    assert demand.active(["es", "en", "pt"]) == ["es", "en"]  # fr and de are not targets
    assert demand.active() == ["es", "fr", "de", "en"]  # no candidate filter: everything seen


def test_explicit_now_and_expiry_cleanup() -> None:
    demand = LanguageDemand([], grace_seconds=2)
    demand.observe(["pt"], now=100.0)
    assert demand.active(["pt"], now=101.9) == ["pt"]
    assert demand.active(["pt"], now=102.1) == []
    assert demand.active(["pt"], now=100.5) == []  # expired entries are dropped, not revived
