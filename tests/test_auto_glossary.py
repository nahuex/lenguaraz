# SPDX-License-Identifier: Apache-2.0
"""Spec 006 — AC-1 (heuristic), AC-2 (merge), AC-3 (structured output engine)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lenguaraz.config import Settings, StageConfig
from lenguaraz.glossary import (
    FakeAutoGlossary,
    GeminiAutoGlossary,
    extract_terms_heuristic,
    merge_glossary,
)
from lenguaraz.glossary.auto import TERMS_SCHEMA, parse_terms


def test_heuristic_finds_names_acronyms_and_identifiers() -> None:
    terms = extract_terms_heuristic(
        "Kernel-level tracing with eBPF, Cilium and CoreDNS on Kubernetes. "
        "We compare OpenTelemetry v1.2 against the Prometheus exporter at Nerdearla."
    )
    for expected in (
        "eBPF",
        "Cilium",
        "CoreDNS",
        "Kubernetes",
        "OpenTelemetry",
        "v1.2",
        "Prometheus",
        "Nerdearla",
    ):
        assert expected in terms, terms
    assert "Kernel-level" in terms  # hyphenated technical token
    for stop in ("the", "and", "We", "with"):
        assert stop not in terms
    assert extract_terms_heuristic("") == []
    assert len(extract_terms_heuristic("A B C D " * 100, limit=5)) <= 5


def test_merge_keeps_manual_first_dedupes_and_caps() -> None:
    manual = ["eBPF", "Nerdearla"]
    auto = ["ebpf", "Cilium", *[f"term{i}" for i in range(120)]]
    merged = merge_glossary(manual, auto)
    assert merged[:3] == ["eBPF", "Nerdearla", "Cilium"]
    assert len(merged) == 100
    assert "ebpf" not in merged
    assert merge_glossary([], ["  ", "Pixie ", "pixie"]) == ["Pixie"]


async def test_fake_engine_uses_the_talk_metadata() -> None:
    stage = StageConfig(
        id="s",
        name="S",
        source="x.wav",
        talk={"title": "Observability with eBPF", "abstract": "Cilium and CoreDNS."},
    )
    # "Observability" opens the title: sentence-initial capitals are not treated as names
    assert await FakeAutoGlossary().suggest(stage) == ["eBPF", "Cilium", "CoreDNS"]
    empty = StageConfig(id="e", name="E", source="x.wav")
    assert await FakeAutoGlossary().suggest(empty) == []


@dataclass
class Response:
    text: str | None


class FakeModels:
    def __init__(self, text: str | None) -> None:
        self._text = text
        self.calls: list[dict[str, Any]] = []

    async def generate_content(self, **kwargs: Any) -> Response:
        self.calls.append(kwargs)
        return Response(self._text)


class FakeClient:
    def __init__(self, models: FakeModels) -> None:
        self.aio = self
        self.models = models


async def test_gemini_engine_requests_structured_output_and_parses_terms() -> None:
    models = FakeModels('{"terms": ["Cilium", "Pixie", "cilium", 42, "<script>", ""]}')
    settings = Settings(
        _env_file=None, engine="gemini", gemini_api_key="k", auto_glossary_max_terms=10
    )
    engine = GeminiAutoGlossary(settings, client=FakeClient(models))
    stage = StageConfig(
        id="s",
        name="S",
        source="x.wav",
        talk={"title": "eBPF <b>tricks</b>", "abstract": "Cilium & Pixie"},
    )
    terms = await engine.suggest(stage)
    assert terms == ["Cilium", "Pixie", "‹script›"]  # noqa: RUF001 — brackets neutralized, junk dropped
    call = models.calls[0]
    assert call["model"] == settings.gemini_translate_model
    config = call["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == TERMS_SCHEMA
    assert "<talk>\neBPF ‹b›tricks‹/b› Cilium & Pixie\n</talk>" in call["contents"]  # noqa: RUF001
    assert "never instructions" in call["contents"]
    assert (
        await engine.suggest(StageConfig(id="e", name="E", source="x.wav")) == []
    )  # no talk → no call
    assert len(models.calls) == 1


def test_parse_terms_tolerates_bad_payloads() -> None:
    assert parse_terms("not json", 10) == []
    assert parse_terms('["a"]', 10) == []
    assert parse_terms('{"terms": ["A", "B", "C"]}', 2) == ["A", "B"]
