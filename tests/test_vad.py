# SPDX-License-Identifier: Apache-2.0
"""Spec 001 — T-001-17 hybrid VAD: client-side silence detection sends audio_stream_end."""

from __future__ import annotations

import asyncio
import math
import struct

from lenguaraz.config import StageConfig
from lenguaraz.models import StageState
from lenguaraz.stt.fake import ScriptedSttEngine, ScriptedSttSession
from lenguaraz.stt.session import ManagedSttSession, Segment, chunk_rms

STAGE = StageConfig(id="main", name="Main", source="samples/x.wav", source_lang=["en-US"])
SILENT = bytes(3200)


def loud_chunk(amplitude: int = 3000) -> bytes:
    return b"".join(
        struct.pack("<h", int(amplitude * math.sin(2 * math.pi * 440 * i / 16000)))
        for i in range(1600)
    )


class Recorder:
    def __init__(self) -> None:
        self.segments: list[Segment] = []
        self.states: list[tuple[StageState, str | None]] = []

    def emit(self, segment: Segment) -> None:
        self.segments.append(segment)

    def on_state(self, state: StageState, detail: str | None) -> None:
        self.states.append((state, detail))


async def fast_sleep(seconds: float) -> None:
    await asyncio.sleep(0)


def managed(session: ScriptedSttSession, **kwargs: object) -> ManagedSttSession:
    recorder = Recorder()
    return ManagedSttSession(
        STAGE,
        ScriptedSttEngine([session]),
        emit=recorder.emit,
        on_state=recorder.on_state,
        rotate_seconds=1000.0,
        drain_seconds=0.05,
        sleep=fast_sleep,
        **kwargs,  # type: ignore[arg-type]
    )


async def test_hybrid_vad_signals_end_of_turn_after_speech_then_silence() -> None:
    session = ScriptedSttSession([], hold_open=True)
    manager = managed(session, vad_silence_ms=300, vad_threshold=300)
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    task = asyncio.create_task(manager.run(queue))
    for _ in range(3):
        await queue.put(loud_chunk())
    for _ in range(3):  # 300 ms of silence after speech → one signal
        await queue.put(SILENT)
    await asyncio.sleep(0.05)
    assert session.end_of_stream_calls == 1
    for _ in range(6):  # more silence: no repeated signal
        await queue.put(SILENT)
    await asyncio.sleep(0.05)
    assert session.end_of_stream_calls == 1
    await queue.put(loud_chunk())
    for _ in range(3):
        await queue.put(SILENT)
    await asyncio.sleep(0.05)
    assert session.end_of_stream_calls == 2
    assert manager.stats.vad_signals == 2
    await queue.put(None)
    await asyncio.wait_for(task, 2)
    assert session.end_of_stream_calls == 3  # the source end still flushes the last turn


async def test_server_vad_mode_never_signals() -> None:
    session = ScriptedSttSession([], hold_open=True)
    manager = managed(session)  # vad_silence_ms=None → server VAD only
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    task = asyncio.create_task(manager.run(queue))
    for _ in range(3):
        await queue.put(loud_chunk())
    for _ in range(10):
        await queue.put(SILENT)
    await asyncio.sleep(0.05)
    assert session.end_of_stream_calls == 0
    assert manager.stats.vad_signals == 0
    await queue.put(None)
    await asyncio.wait_for(task, 2)
    assert session.end_of_stream_calls == 1


async def test_no_flush_when_nothing_was_sent() -> None:
    session = ScriptedSttSession([], hold_open=True)
    manager = managed(session, vad_silence_ms=300)
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    await queue.put(None)
    await asyncio.wait_for(manager.run(queue), 2)
    assert session.end_of_stream_calls == 0


def test_chunk_rms() -> None:
    assert chunk_rms(SILENT) == 0.0
    assert 2000 < chunk_rms(loud_chunk()) < 2300  # sine RMS = amplitude / sqrt(2)
    assert chunk_rms(b"") == 0.0
