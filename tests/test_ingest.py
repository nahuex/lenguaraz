# SPDX-License-Identifier: Apache-2.0
"""Spec 001 — FR-001-02, AC-3 (3,200-byte chunks, real-time pacing, clean stop)."""

from __future__ import annotations

import asyncio
import math
import os
import shutil
import struct
import wave
from pathlib import Path

import pytest

from lenguaraz.ingest import CHUNK_BYTES, IngestError, open_source
from lenguaraz.ingest.ffmpeg import FfmpegSource, build_ffmpeg_args
from lenguaraz.ingest.wav import WavFileSource, is_native_wav

FFMPEG = os.environ.get("FFMPEG_BIN") or shutil.which("ffmpeg")


def write_wav(path: Path, seconds: float, *, rate: int = 16000, channels: int = 1) -> Path:
    frames = int(rate * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        samples = (int(8000 * math.sin(2 * math.pi * 440 * i / rate)) for i in range(frames))
        handle.writeframes(b"".join(struct.pack("<h", s) * channels for s in samples))
    return path


async def collect(source, limit: int | None = None) -> list[bytes]:  # type: ignore[no-untyped-def]
    out: list[bytes] = []
    async for chunk in source.chunks():
        out.append(chunk)
        if limit is not None and len(out) >= limit:
            await source.close()
            break
    return out


async def test_wav_source_yields_fixed_chunks(tmp_path: Path) -> None:
    path = write_wav(tmp_path / "half.wav", 0.55)  # 5 full chunks + 1 partial (padded)
    chunks = await collect(WavFileSource(str(path), realtime=False))
    assert len(chunks) == 6
    assert all(len(c) == CHUNK_BYTES for c in chunks)
    assert chunks[-1].endswith(bytes(1000))  # zero padding on the tail


async def test_wav_source_paces_in_real_time(tmp_path: Path) -> None:
    path = write_wav(tmp_path / "one.wav", 1.0)
    now = [0.0]
    delays: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)
        now[0] += seconds

    source = WavFileSource(str(path), realtime=True, sleep=fake_sleep, clock=lambda: now[0])
    chunks = await collect(source)
    assert len(chunks) == 10
    assert len(delays) == 9  # first chunk is due immediately
    assert all(abs(d - 0.1) < 1e-6 for d in delays)


async def test_wav_source_loops_until_closed(tmp_path: Path) -> None:
    path = write_wav(tmp_path / "short.wav", 0.3)
    chunks = await collect(WavFileSource(str(path), realtime=False, loop=True), limit=8)
    assert len(chunks) == 8


async def test_wav_source_rejects_other_formats(tmp_path: Path) -> None:
    path = write_wav(tmp_path / "phone.wav", 0.2, rate=8000)
    assert is_native_wav(str(path)) is False
    with pytest.raises(IngestError, match="8000 Hz"):
        await collect(WavFileSource(str(path), realtime=False))
    with pytest.raises(IngestError, match="cannot open"):
        await collect(WavFileSource(str(tmp_path / "missing.wav"), realtime=False))


def test_open_source_picks_stdlib_for_native_wav_and_ffmpeg_otherwise(tmp_path: Path) -> None:
    native = write_wav(tmp_path / "ok.wav", 0.1)
    assert isinstance(open_source(str(native)), WavFileSource)
    stereo = write_wav(tmp_path / "stereo.wav", 0.1, channels=2)
    assert isinstance(open_source(str(stereo)), FfmpegSource)
    assert isinstance(open_source("srt://10.0.0.5:9000?mode=caller"), FfmpegSource)
    assert isinstance(open_source("https://cdn.example/live/index.m3u8"), FfmpegSource)


def test_ffmpeg_args_for_files_and_streams() -> None:
    file_args = build_ffmpeg_args("samples/talk.mp3", realtime=True, loop=True)
    assert file_args[0] == "ffmpeg"
    assert "-re" in file_args
    assert file_args[file_args.index("-stream_loop") + 1] == "-1"
    assert file_args[file_args.index("-i") + 1] == "samples/talk.mp3"
    assert file_args[-1] == "pipe:1"
    assert file_args[file_args.index("-ar") + 1] == "16000"
    assert file_args[file_args.index("-ac") + 1] == "1"
    assert file_args[file_args.index("-f") + 1] == "s16le"

    stream_args = build_ffmpeg_args("rtmp://host/live/key", ffmpeg_bin="/opt/ffmpeg", loop=True)
    assert stream_args[0] == "/opt/ffmpeg"
    assert "-re" not in stream_args  # live streams already run at wall-clock speed
    assert "-stream_loop" not in stream_args


async def test_ffmpeg_missing_binary_is_an_ingest_error() -> None:
    source = FfmpegSource("x.wav", ffmpeg_bin="definitely-not-ffmpeg-binary")
    with pytest.raises(IngestError, match="ffmpeg not found"):
        await collect(source)


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not on PATH (set FFMPEG_BIN)")
async def test_ffmpeg_decodes_a_stereo_wav_and_stops_cleanly(tmp_path: Path) -> None:
    assert FFMPEG is not None
    path = write_wav(tmp_path / "stereo.wav", 0.5, rate=44100, channels=2)
    source = FfmpegSource(str(path), ffmpeg_bin=FFMPEG, realtime=False)
    chunks = await collect(source)
    assert 4 <= len(chunks) <= 6  # ~0.5 s of 16 kHz mono audio
    assert all(len(c) == CHUNK_BYTES for c in chunks)
    assert source._process is not None
    assert source._process.returncode == 0

    long_path = write_wav(tmp_path / "long.wav", 5.0, rate=44100, channels=2)
    source = FfmpegSource(str(long_path), ffmpeg_bin=FFMPEG, realtime=True)
    chunks = await collect(source, limit=3)
    assert len(chunks) == 3
    await asyncio.sleep(0.05)
    assert source._process is not None and source._process.returncode is not None


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not on PATH (set FFMPEG_BIN)")
async def test_ffmpeg_bad_source_reports_stderr(tmp_path: Path) -> None:
    assert FFMPEG is not None
    with pytest.raises(IngestError, match="ffmpeg exited"):
        await collect(FfmpegSource(str(tmp_path / "missing.mp3"), ffmpeg_bin=FFMPEG))
