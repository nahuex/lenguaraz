# SPDX-License-Identifier: Apache-2.0
"""Fake STT engines: a scripted session for tests and a dry-run engine for ``ENGINE=fake``.

Neither touches the network (Constitution Art. XII.2). The dry-run engine turns the
reference transcript that sits next to a sample (``<source>.txt``, one sentence per
line) into word-by-word interims and sentence finals, paced by the audio it receives,
so the whole UI can be exercised without credentials.
"""

from __future__ import annotations

import asyncio
import itertools
from collections.abc import AsyncIterator, Iterable, Sequence
from pathlib import Path

from lenguaraz.config import StageConfig
from lenguaraz.stt.base import SttEvent, SttEventKind

BYTES_PER_MS = 32  # 16 kHz x 2 bytes x 1 channel

DEMO_SENTENCES: dict[str, list[str]] = {
    "en": [
        "Welcome to the Lenguaraz dry run, where captions come from a fake engine.",
        "Every stage gets its own transcription session and its own state.",
        "Interim lines update word by word, and a final line commits the sentence.",
        "Configure a real Gemini API key to replace this script with live speech.",
    ],
    "es": [
        "Bienvenidos a la prueba en seco de Lenguaraz, con subtítulos de un motor falso.",
        "Cada escenario tiene su propia sesión de transcripción y su propio estado.",
        "Las líneas provisorias se actualizan palabra por palabra y la final confirma la oración.",
        "Configurá una clave real de Gemini para reemplazar este guion por voz en vivo.",
    ],
}


class ScriptedSttSession:
    """Emits a fixed script of events, optionally with delays; records what was sent."""

    def __init__(
        self,
        script: Iterable[SttEvent | tuple[float, SttEvent]],
        *,
        session_id: str = "scripted",
        send_error: Exception | None = None,
        hold_open: bool = False,
    ) -> None:
        self.session_id = session_id
        self._script = [(0.0, item) if isinstance(item, SttEvent) else item for item in script]
        self._send_error = send_error
        self._hold_open = hold_open
        self.sent = bytearray()
        self.ended = False
        self.end_of_stream_calls = 0
        self.closed = False
        self._closed_event = asyncio.Event()

    async def send(self, chunk: bytes) -> None:
        if self._send_error is not None:
            raise self._send_error
        self.sent.extend(chunk)

    async def end_of_stream(self) -> None:
        self.ended = True
        self.end_of_stream_calls += 1

    async def events(self) -> AsyncIterator[SttEvent]:
        for delay, event in self._script:
            if self.closed:
                return
            if delay:
                await asyncio.sleep(delay)
            yield event
        if self._hold_open:
            await self._closed_event.wait()

    async def close(self) -> None:
        self.closed = True
        self._closed_event.set()


class ScriptedSttEngine:
    """Hands out prepared sessions in order; an ``Exception`` entry is raised by ``open``."""

    name = "scripted"

    def __init__(self, sessions: Sequence[ScriptedSttSession | Exception]) -> None:
        self._sessions = list(sessions)
        self.opened: list[StageConfig] = []

    async def open(self, stage: StageConfig) -> ScriptedSttSession:
        self.opened.append(stage)
        if not self._sessions:
            raise RuntimeError("scripted engine has no sessions left")
        item = self._sessions.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeSttSession:
    """Dry-run session: interims per word and a final per sentence, paced by audio bytes."""

    def __init__(
        self,
        sentences: Sequence[str],
        language: str,
        *,
        session_id: str = "fake",
        words_per_second: float = 2.5,
        final_delay_ms: int = 300,
        gap_ms: int = 600,
        loop: bool = True,
    ) -> None:
        self.session_id = session_id
        self._sentences = list(sentences) or DEMO_SENTENCES["en"]
        self._language = language
        self._ms_per_word = 1000.0 / words_per_second
        self._final_delay_ms = final_delay_ms
        self._gap_ms = gap_ms
        self._loop = loop
        self._audio_ms = 0.0
        self.end_of_stream_calls = 0
        self._closed = False
        self._progress = asyncio.Event()

    async def send(self, chunk: bytes) -> None:
        self._audio_ms += len(chunk) / BYTES_PER_MS
        self._progress.set()

    async def end_of_stream(self) -> None:
        # Hybrid VAD signals turn ends; the dry-run script keeps pacing on audio.
        self.end_of_stream_calls += 1

    async def close(self) -> None:
        self._closed = True
        self._progress.set()

    async def _wait_until(self, target_ms: float) -> bool:
        """Block until the audio position reaches ``target_ms``. False if the stream ended."""
        while self._audio_ms < target_ms:
            if self._closed:
                return False
            self._progress.clear()
            await self._progress.wait()
        return not self._closed

    async def events(self) -> AsyncIterator[SttEvent]:
        cursor = 0.0
        sequence = itertools.cycle(self._sentences) if self._loop else iter(self._sentences)
        for sentence in sequence:
            words = sentence.split()
            for index in range(1, len(words)):
                if not await self._wait_until(cursor + index * self._ms_per_word):
                    return
                yield SttEvent.interim(" ".join(words[:index]), self._language)
            spoken_ms = len(words) * self._ms_per_word
            if not await self._wait_until(cursor + spoken_ms + self._final_delay_ms):
                return
            yield SttEvent.final(sentence, self._language)
            cursor += spoken_ms + self._gap_ms


class FakeSttEngine:
    """``ENGINE=fake``: no credentials, no network, deterministic captions."""

    name = "fake"

    def __init__(self, *, words_per_second: float = 2.5, loop: bool = True) -> None:
        self._words_per_second = words_per_second
        self._loop = loop

    async def open(self, stage: StageConfig) -> FakeSttSession:
        language = stage.primary_source_lang or "en"
        sentences = reference_sentences(stage.source) or DEMO_SENTENCES.get(
            language, DEMO_SENTENCES["en"]
        )
        return FakeSttSession(
            sentences,
            language,
            session_id=f"fake-{stage.id}",
            words_per_second=self._words_per_second,
            loop=self._loop,
        )


def reference_sentences(source: str) -> list[str]:
    """Sentences from the reference transcript next to a sample file, if any."""
    path = Path(source)
    if "://" in source or path.suffix.lower() not in {".wav", ".mp3", ".flac", ".ogg", ".m4a"}:
        return []
    reference = path.with_suffix(".txt")
    if not reference.is_file():
        return []
    lines = [line.strip() for line in reference.read_text(encoding="utf-8").splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


__all__ = [
    "DEMO_SENTENCES",
    "FakeSttEngine",
    "FakeSttSession",
    "ScriptedSttEngine",
    "ScriptedSttSession",
    "SttEventKind",
    "reference_sentences",
]
