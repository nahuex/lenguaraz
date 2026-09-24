# SPDX-License-Identifier: Apache-2.0
"""Standard-library WAV reader with real-time pacing (no ffmpeg required)."""

from __future__ import annotations

import asyncio
import contextlib
import time
import wave
from collections.abc import AsyncIterator, Awaitable, Callable

from lenguaraz.ingest.base import (
    BYTES_PER_MS,
    BYTES_PER_SAMPLE,
    CHANNELS,
    CHUNK_BYTES,
    SAMPLE_RATE,
    IngestError,
)


def is_native_wav(path: str) -> bool:
    """True when the file is a WAV we can stream without transcoding."""
    try:
        with wave.open(path, "rb") as handle:
            return (
                handle.getframerate() == SAMPLE_RATE
                and handle.getnchannels() == CHANNELS
                and handle.getsampwidth() == BYTES_PER_SAMPLE
            )
    except (wave.Error, OSError, EOFError):
        return False


class WavFileSource:
    def __init__(
        self,
        path: str,
        *,
        realtime: bool = True,
        loop: bool = False,
        chunk_bytes: int = CHUNK_BYTES,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._path = path
        self._realtime = realtime
        self._loop = loop
        self._chunk_bytes = chunk_bytes
        self._sleep = sleep
        self._clock = clock
        self._closed = False

    async def chunks(self) -> AsyncIterator[bytes]:
        try:
            handle = wave.open(self._path, "rb")  # noqa: SIM115 — closed by contextlib below
        except (wave.Error, OSError, EOFError) as exc:
            raise IngestError(f"cannot open WAV {self._path}: {exc}") from exc
        with contextlib.closing(handle):
            if (
                handle.getframerate() != SAMPLE_RATE
                or handle.getnchannels() != CHANNELS
                or handle.getsampwidth() != BYTES_PER_SAMPLE
            ):
                raise IngestError(
                    f"{self._path} is {handle.getframerate()} Hz / {handle.getnchannels()} ch / "
                    f"{handle.getsampwidth() * 8}-bit; expected 16000 Hz mono 16-bit "
                    "(other formats are decoded through ffmpeg)"
                )
            frames_per_chunk = self._chunk_bytes // (BYTES_PER_SAMPLE * CHANNELS)
            start = self._clock()
            sent = 0
            while not self._closed:
                data = handle.readframes(frames_per_chunk)
                if not data:
                    if not self._loop:
                        return
                    handle.rewind()
                    continue
                if len(data) < self._chunk_bytes:
                    data = data + bytes(self._chunk_bytes - len(data))
                if self._realtime:
                    due = start + (sent / BYTES_PER_MS) / 1000.0
                    delay = due - self._clock()
                    if delay > 0:
                        await self._sleep(delay)
                sent += len(data)
                yield data

    async def close(self) -> None:
        self._closed = True
