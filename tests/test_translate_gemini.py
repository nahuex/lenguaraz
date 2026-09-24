# SPDX-License-Identifier: Apache-2.0
"""Spec 002 — FR-002-01/09: Interactions streaming engine with a scripted client (no network)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import pytest
from google.genai import errors

from lenguaraz.config import Settings
from lenguaraz.translate.base import TranslationError, TranslationRequest
from lenguaraz.translate.gemini import GeminiTranslationEngine, classify


@dataclass
class Delta:
    type: str
    text: str | None = None


@dataclass
class Usage:
    total_tokens: int
    total_input_tokens: int
    total_output_tokens: int


@dataclass
class Interaction:
    usage: Usage | None


@dataclass
class Event:
    event_type: str
    delta: Delta | None = None
    interaction: Interaction | None = None


class FakeStream:
    def __init__(self, events: list[Event], error: Exception | None = None) -> None:
        self._events = events
        self._error = error

    def __aiter__(self) -> AsyncIterator[Event]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[Event]:
        for event in self._events:
            yield event
        if self._error is not None:
            raise self._error


class FakeInteractions:
    def __init__(
        self,
        events: list[Event],
        *,
        error: Exception | None = None,
        raise_on_create: Exception | None = None,
    ) -> None:
        self._events = events
        self._error = error
        self._raise = raise_on_create
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> FakeStream:
        self.calls.append(kwargs)
        if self._raise is not None:
            raise self._raise
        return FakeStream(self._events, self._error)


class FakeClient:
    def __init__(self, interactions: FakeInteractions) -> None:
        self.aio = self
        self.interactions = interactions


def settings(**overrides: Any) -> Settings:
    overrides.setdefault("gemini_translate_api", "interactions")
    return Settings(_env_file=None, engine="gemini", gemini_api_key="AIza-test", **overrides)


REQUEST = TranslationRequest(
    text="We attach small programs to kernel hooks.",
    source_lang="en-US",
    target_lang="es",
    glossary=("eBPF",),
)


async def test_streams_text_deltas_and_records_usage() -> None:
    interactions = FakeInteractions(
        [
            Event("interaction.created"),
            Event("step.start"),
            Event("step.delta", Delta("thought_signature")),
            Event("step.delta", Delta("text", "Adjuntamos ")),
            Event("step.delta", Delta("text", "pequeños programas a hooks del kernel.")),
            Event("step.stop"),
            Event("interaction.completed", interaction=Interaction(Usage(120, 100, 20))),
        ]
    )
    engine = GeminiTranslationEngine(
        settings(gemini_translate_model="gemini-3.5-flash-lite"), client=FakeClient(interactions)
    )
    deltas: list[str] = []
    outcome = await engine.translate(REQUEST, on_delta=deltas.append)
    assert outcome.text == "Adjuntamos pequeños programas a hooks del kernel."
    assert deltas == ["Adjuntamos ", "pequeños programas a hooks del kernel."]
    assert outcome.usage.total_tokens == 120
    assert outcome.usage.input_tokens == 100 and outcome.usage.output_tokens == 20
    assert outcome.usage.calls == 1
    assert outcome.ttft_ms is not None and outcome.ttft_ms >= 0

    call = interactions.calls[0]
    assert call["model"] == "gemini-3.5-flash-lite"
    assert call["stream"] is True and call["store"] is False
    assert call["generation_config"] == {"thinking_level": "minimal", "max_output_tokens": 512}
    assert "from English into Spanish" in call["system_instruction"]
    assert "<glossary>\neBPF\n</glossary>" in call["input"]
    assert "<text>\nWe attach small programs to kernel hooks.\n</text>" in call["input"]


async def test_quota_error_is_retryable_and_bad_request_is_not() -> None:
    quota = errors.APIError(
        429, {"error": {"message": "Resource exhausted", "status": "RESOURCE_EXHAUSTED"}}
    )
    engine = GeminiTranslationEngine(
        settings(), client=FakeClient(FakeInteractions([], raise_on_create=quota))
    )
    with pytest.raises(TranslationError) as info:
        await engine.translate(REQUEST)
    assert info.value.code == 429 and info.value.retryable is True
    assert "quota exhausted" in str(info.value)

    bad = errors.APIError(400, {"error": {"message": "bad", "status": "INVALID_ARGUMENT"}})
    assert classify(bad).retryable is False
    assert classify(ConnectionError("reset")).retryable is True


async def test_mid_stream_error_and_empty_output() -> None:
    boom = errors.APIError(503, {"error": {"message": "unavailable", "status": "UNAVAILABLE"}})
    engine = GeminiTranslationEngine(
        settings(),
        client=FakeClient(
            FakeInteractions([Event("step.delta", Delta("text", "Hola"))], error=boom)
        ),
    )
    with pytest.raises(TranslationError) as info:
        await engine.translate(REQUEST)
    assert info.value.code == 503

    empty = GeminiTranslationEngine(
        settings(), client=FakeClient(FakeInteractions([Event("step.stop")]))
    )
    with pytest.raises(TranslationError, match="empty translation"):
        await empty.translate(REQUEST)


async def test_output_is_cleaned() -> None:
    interactions = FakeInteractions(
        [
            Event("step.delta", Delta("text", 'Translation: "Hola a todos."')),
            Event("interaction.completed", interaction=Interaction(None)),
        ]
    )
    engine = GeminiTranslationEngine(settings(), client=FakeClient(interactions))
    outcome = await engine.translate(REQUEST)
    assert outcome.text == "Hola a todos."
    assert outcome.usage.calls == 1 and outcome.usage.total_tokens == 0


@dataclass
class Metadata:
    prompt_token_count: int
    candidates_token_count: int
    total_token_count: int


@dataclass
class Chunk:
    text: str | None = None
    usage_metadata: Metadata | None = None


class FakeModels:
    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks
        self.calls: list[dict[str, Any]] = []

    async def generate_content_stream(self, **kwargs: Any) -> FakeStream:
        self.calls.append(kwargs)
        return FakeStream(self._chunks)  # type: ignore[arg-type]


class FakeModelsClient:
    def __init__(self, models: FakeModels) -> None:
        self.aio = self
        self.models = models


async def test_generate_content_stream_transport_is_the_default() -> None:
    models = FakeModels(
        [
            Chunk(text="Hola "),
            Chunk(text="a todos.", usage_metadata=Metadata(210, 12, 222)),
        ]
    )
    engine = GeminiTranslationEngine(
        settings(gemini_translate_api="generate_content", gemini_translate_thinking="low"),
        client=FakeModelsClient(models),
    )
    deltas: list[str] = []
    outcome = await engine.translate(REQUEST, on_delta=deltas.append)
    assert outcome.text == "Hola a todos." and deltas == ["Hola ", "a todos."]
    assert outcome.usage.input_tokens == 210 and outcome.usage.output_tokens == 12
    call = models.calls[0]
    assert call["model"] == "gemini-3.5-flash-lite" and call["contents"].endswith("</text>")
    config = call["config"]
    assert "from English into Spanish" in config.system_instruction
    assert config.max_output_tokens == 512
    assert str(config.thinking_config.thinking_level).upper().endswith("LOW")
    assert Settings(_env_file=None, engine="fake").gemini_translate_api == "generate_content"
