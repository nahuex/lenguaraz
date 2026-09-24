# SPDX-License-Identifier: Apache-2.0
"""Audio source interface and factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol

SAMPLE_RATE = 16_000
BYTES_PER_SAMPLE = 2
CHANNELS = 1
BYTES_PER_MS = SAMPLE_RATE * BYTES_PER_SAMPLE * CHANNELS // 1000  # 32
CHUNK_MS = 100
CHUNK_BYTES = BYTES_PER_MS * CHUNK_MS  # 3,200 (GT-3.2)


class IngestError(Exception):
    """The source cannot be opened or decoded."""


class AudioSource(Protocol):
    """Yields raw s16le mono 16 kHz audio in fixed-size chunks."""

    def chunks(self) -> AsyncIterator[bytes]: ...

    async def close(self) -> None: ...


def is_local_file(source: str) -> bool:
    return "://" not in source and Path(source).suffix != "" and Path(source).is_file()


def open_source(
    source: str, *, ffmpeg_bin: str = "ffmpeg", realtime: bool = True, loop: bool = False
) -> AudioSource:
    """Pick the cheapest source that can decode ``source``.

    Local 16 kHz mono WAV files are read with the standard library (no ffmpeg needed,
    which keeps the dry run and the fresh-clone test dependency-free). Everything else
    (other formats, HLS, RTMP, SRT, devices) goes through ffmpeg.
    """
    from lenguaraz.ingest.ffmpeg import FfmpegSource
    from lenguaraz.ingest.wav import WavFileSource, is_native_wav

    if is_local_file(source) and is_native_wav(source):
        return WavFileSource(source, realtime=realtime, loop=loop)
    return FfmpegSource(source, ffmpeg_bin=ffmpeg_bin, realtime=realtime, loop=loop)
