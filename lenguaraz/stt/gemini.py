# SPDX-License-Identifier: Apache-2.0
"""Gemini Live API transcription engine.

Every field below was verified through the Gemini Docs MCP and against the installed
``google-genai`` SDK (plan 001 §2):

- ``client.aio.live.connect(model=…, config=LiveConnectConfig(...))``
- ``LiveConnectConfig(response_modalities=["TEXT"], input_audio_transcription=
  AudioTranscriptionConfig(language_codes=[…], custom_vocabulary=[…], mode="SMART"))``
- ``session.send_realtime_input(audio=Blob(data=…, mime_type="audio/pcm;rate=16000"))``
  and ``send_realtime_input(audio_stream_end=True)``
- ``message.server_content.interim_input_transcription`` / ``.input_transcription``
- ``message.go_away.time_left`` and ``message.usage_metadata``
"""

from __future__ import annotations

import contextlib
import logging
import re
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from google.genai import errors, types

from lenguaraz.config import Settings, StageConfig
from lenguaraz.stt.base import SttEvent

log = logging.getLogger("lenguaraz.stt.gemini")

AUDIO_MIME = "audio/pcm;rate=16000"
MAX_VOCABULARY = 100
RETRYABLE_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
_DURATION = re.compile(r"^([0-9.]+)s$")


def build_live_config(stage: StageConfig, settings: Settings) -> types.LiveConnectConfig:
    vocabulary = stage.glossary[:MAX_VOCABULARY]
    transcription = types.AudioTranscriptionConfig(
        language_codes=list(stage.source_lang),
        custom_vocabulary=vocabulary or None,
        mode=types.AudioTranscriptionConfigMode(settings.stt_mode.value),
    )
    return types.LiveConnectConfig(
        response_modalities=[types.Modality.TEXT],
        input_audio_transcription=transcription,
    )


def parse_time_left(value: Any) -> float | None:
    """``GoAway.time_left`` arrives as a protobuf Duration string such as ``"12.5s"``."""
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if hasattr(value, "total_seconds"):
        return float(value.total_seconds())
    match = _DURATION.match(str(value).strip())
    return float(match.group(1)) if match else None


def classify_error(exc: BaseException) -> SttEvent:
    code = getattr(exc, "code", None)
    status = getattr(exc, "status", None)
    message = getattr(exc, "message", None) or str(exc)
    retryable = code is None or code in RETRYABLE_CODES
    if isinstance(code, int) and 1000 <= code <= 4999:
        # WebSocket close codes (e.g. 1008 "The operation was aborted" after ~60 s without
        # audio, 1011 server error): the session is gone, reopening it is the right move.
        retryable = True
    if message.strip().startswith("1000"):
        message = f"connection closed ({message.strip()})"
    if code == 429:
        message = f"quota exhausted (429 {status or 'RESOURCE_EXHAUSTED'}): {message}"
    elif code in (401, 403):
        message = f"authentication failed ({code}): {message}"
    elif code == 400:
        message = f"rejected by the API (400): {message}"
    return SttEvent.failure(message, code=code, retryable=retryable)


class GeminiSttSession:
    def __init__(
        self, client: Any, model: str, config: types.LiveConnectConfig, *, session_id: str
    ) -> None:
        self._client = client
        self._model = model
        self._config = config
        self.session_id = session_id
        self._context: Any = None
        self._session: Any = None

    async def connect(self) -> None:
        self._context = self._client.aio.live.connect(model=self._model, config=self._config)
        self._session = await self._context.__aenter__()

    async def send(self, chunk: bytes) -> None:
        await self._session.send_realtime_input(audio=types.Blob(data=chunk, mime_type=AUDIO_MIME))

    async def end_of_stream(self) -> None:
        await self._session.send_realtime_input(audio_stream_end=True)

    async def events(self) -> AsyncIterator[SttEvent]:
        try:
            async for message in self._session.receive():
                for event in self._translate(message):
                    yield event
        except errors.APIError as exc:
            yield classify_error(exc)
        except (ConnectionError, OSError, TimeoutError) as exc:
            yield SttEvent.failure(f"connection lost: {exc}", retryable=True)

    @staticmethod
    def _translate(message: Any) -> list[SttEvent]:
        events: list[SttEvent] = []
        usage = getattr(message, "usage_metadata", None)
        if usage is not None:
            events.append(
                SttEvent.usage(
                    usage.prompt_token_count or 0,
                    usage.response_token_count or 0,
                    usage.total_token_count or 0,
                )
            )
        content = getattr(message, "server_content", None)
        if content is not None:
            interim = getattr(content, "interim_input_transcription", None)
            if interim is not None and interim.text:
                events.append(SttEvent.interim(interim.text, interim.language_code))
            final = getattr(content, "input_transcription", None)
            if final is not None and final.text:
                events.append(SttEvent.final(final.text, final.language_code))
        go_away = getattr(message, "go_away", None)
        if go_away is not None:
            events.append(SttEvent.go_away(parse_time_left(go_away.time_left)))
        return events

    async def close(self) -> None:
        context, self._context, self._session = self._context, None, None
        if context is not None:
            with contextlib.suppress(Exception):
                await context.__aexit__(None, None, None)


class GeminiSttEngine:
    name = "gemini"

    def __init__(self, settings: Settings, *, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client
        self.last_config: types.LiveConnectConfig | None = None

    def client(self) -> Any:
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._settings.api_key())
        return self._client

    async def open(self, stage: StageConfig) -> GeminiSttSession:
        config = build_live_config(stage, self._settings)
        self.last_config = config
        session = GeminiSttSession(
            self.client(),
            self._settings.gemini_stt_model,
            config,
            session_id=f"{stage.id}-{uuid4().hex[:8]}",
        )
        try:
            await session.connect()
        except errors.APIError as exc:
            event = classify_error(exc)
            raise ConnectionError(event.error) from exc
        log.info(
            "live session opened",
            extra={
                "stage_id": stage.id,
                "session_id": session.session_id,
                "component": "transcription",
            },
        )
        return session
