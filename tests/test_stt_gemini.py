# SPDX-License-Identifier: Apache-2.0
"""Spec 001 — FR-001-03 with a double of the Gen AI SDK client (no network, no quota)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from google.genai import errors, types

from lenguaraz.config import Settings, StageConfig
from lenguaraz.engines import build_stt_engine
from lenguaraz.stt.base import SttEventKind
from lenguaraz.stt.gemini import (
    GeminiSttEngine,
    build_live_config,
    classify_error,
    parse_time_left,
)

STAGE = StageConfig(
    id="main",
    name="Main",
    source="x.wav",
    source_lang=["en-US"],
    glossary=[f"term{i}" for i in range(100)],
)


def settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, engine="gemini", gemini_api_key="AIza-test", **overrides)


class FakeLiveSession:
    def __init__(self, messages: list[Any], *, raise_after: BaseException | None = None) -> None:
        self.messages = messages
        self.raise_after = raise_after
        self.sent: list[Any] = []
        self.stream_ended = False

    async def send_realtime_input(self, **kwargs: Any) -> None:
        if kwargs.get("audio_stream_end"):
            self.stream_ended = True
        else:
            self.sent.append(kwargs)

    async def receive(self) -> AsyncIterator[Any]:
        for message in self.messages:
            yield message
        if self.raise_after is not None:
            raise self.raise_after


class FakeConnectContext:
    def __init__(self, session: FakeLiveSession, recorder: dict[str, Any]) -> None:
        self._session = session
        self._recorder = recorder

    async def __aenter__(self) -> FakeLiveSession:
        self._recorder["entered"] = True
        return self._session

    async def __aexit__(self, *exc: object) -> None:
        self._recorder["exited"] = True


class FakeClient:
    def __init__(self, session: FakeLiveSession) -> None:
        self.recorder: dict[str, Any] = {}
        self._session = session
        self.aio = self
        self.live = self

    def connect(self, *, model: str, config: types.LiveConnectConfig) -> FakeConnectContext:
        self.recorder["model"] = model
        self.recorder["config"] = config
        return FakeConnectContext(self._session, self.recorder)


def message(**kwargs: Any) -> types.LiveServerMessage:
    return types.LiveServerMessage(**kwargs)


def test_live_config_uses_verified_fields_only() -> None:
    config = build_live_config(STAGE, settings(stt_mode="SMART"))
    assert config.response_modalities == ["TEXT"]
    transcription = config.input_audio_transcription
    assert transcription is not None
    assert transcription.language_codes == ["en-US"]
    assert transcription.custom_vocabulary is not None
    assert len(transcription.custom_vocabulary) == 100  # capped (GT-2.2: best results <= 100)
    assert str(transcription.mode).endswith("SMART")
    auto = build_live_config(StageConfig(id="a", name="A", source="x.wav"), settings())
    assert auto.input_audio_transcription is not None
    assert auto.input_audio_transcription.language_codes == []
    assert auto.input_audio_transcription.custom_vocabulary is None


async def test_session_maps_server_messages_to_events() -> None:
    fake = FakeLiveSession(
        [
            message(
                server_content=types.LiveServerContent(
                    interim_input_transcription=types.Transcription(
                        text="hel", language_code="en-US"
                    )
                )
            ),
            message(
                server_content=types.LiveServerContent(
                    input_transcription=types.Transcription(
                        text="Hello world.", language_code="en-US"
                    )
                ),
                usage_metadata=types.UsageMetadata(
                    prompt_token_count=250, response_token_count=12, total_token_count=262
                ),
            ),
            message(go_away=types.LiveServerGoAway(time_left="12.5s")),
        ]
    )
    client = FakeClient(fake)
    engine = GeminiSttEngine(settings(gemini_stt_model="gemini-3.5-transcribe-live"), client=client)
    session = await engine.open(STAGE)
    assert client.recorder["model"] == "gemini-3.5-transcribe-live"
    assert client.recorder["config"] is engine.last_config
    assert session.session_id.startswith("main-")

    await session.send(bytes(3200))
    await session.end_of_stream()
    assert fake.sent[0]["audio"].mime_type == "audio/pcm;rate=16000"
    assert len(fake.sent[0]["audio"].data) == 3200
    assert fake.stream_ended is True

    events = [event async for event in session.events()]
    kinds = [e.kind for e in events]
    assert kinds == [
        SttEventKind.INTERIM,
        SttEventKind.USAGE,
        SttEventKind.FINAL,
        SttEventKind.GO_AWAY,
    ]
    assert events[0].text == "hel" and events[0].language_code == "en-US"
    assert events[1].total_tokens == 262 and events[1].prompt_tokens == 250
    assert events[2].text == "Hello world."
    assert events[3].time_left_s == 12.5
    await session.close()
    assert client.recorder["exited"] is True


async def test_api_errors_become_error_events_with_retryability() -> None:
    quota = errors.APIError(
        429, {"error": {"message": "Resource exhausted", "status": "RESOURCE_EXHAUSTED"}}
    )
    fake = FakeLiveSession([], raise_after=quota)
    engine = GeminiSttEngine(settings(), client=FakeClient(fake))
    session = await engine.open(STAGE)
    events = [event async for event in session.events()]
    assert len(events) == 1
    assert events[0].kind is SttEventKind.ERROR
    assert events[0].code == 429 and events[0].retryable is True
    assert "quota exhausted" in (events[0].error or "")

    bad_key = errors.APIError(
        400, {"error": {"message": "API key not valid", "status": "INVALID_ARGUMENT"}}
    )
    event = classify_error(bad_key)
    assert event.retryable is False and event.code == 400
    assert classify_error(ConnectionError("reset")).retryable is True


async def test_connect_failure_surfaces_as_connection_error() -> None:
    class RefusingClient(FakeClient):
        def connect(self, *, model: str, config: types.LiveConnectConfig) -> FakeConnectContext:
            raise errors.APIError(
                403, {"error": {"message": "forbidden", "status": "PERMISSION_DENIED"}}
            )

    engine = GeminiSttEngine(settings(), client=RefusingClient(FakeLiveSession([])))
    with pytest.raises(ConnectionError, match="authentication failed \\(403\\)"):
        await engine.open(STAGE)


def test_parse_time_left() -> None:
    assert parse_time_left("5s") == 5.0
    assert parse_time_left("0.25s") == 0.25
    assert parse_time_left(7) == 7.0
    assert parse_time_left(None) is None
    assert parse_time_left("weird") is None


def test_engine_factory_picks_gemini_without_creating_a_client() -> None:
    engine = build_stt_engine(settings())
    assert isinstance(engine, GeminiSttEngine)
