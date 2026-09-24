# SPDX-License-Identifier: Apache-2.0
"""Spec 003 — AC-1 (make-before-break + drain), AC-2 (dedupe), AC-3 (open failure keeps old)."""

from __future__ import annotations

import asyncio

from lenguaraz.config import StageConfig
from lenguaraz.models import StageState
from lenguaraz.stt.base import SttEvent
from lenguaraz.stt.fake import ScriptedSttEngine, ScriptedSttSession
from lenguaraz.stt.session import ManagedSttSession, Segment, normalize_text

STAGE = StageConfig(id="main", name="Main", source="samples/x.wav", source_lang=["en-US"])
CHUNK = bytes(3200)


async def fast_sleep(seconds: float) -> None:
    await asyncio.sleep(0)


class Recorder:
    def __init__(self) -> None:
        self.segments: list[Segment] = []
        self.states: list[tuple[StageState, str | None]] = []

    def emit(self, segment: Segment) -> None:
        self.segments.append(segment)

    def on_state(self, state: StageState, detail: str | None) -> None:
        self.states.append((state, detail))


def managed(engine: ScriptedSttEngine, recorder: Recorder, **kwargs: object) -> ManagedSttSession:
    kwargs.setdefault("sleep", fast_sleep)
    kwargs.setdefault("rotate_seconds", 1000.0)
    kwargs.setdefault("drain_seconds", 0.3)
    return ManagedSttSession(
        STAGE,
        engine,
        emit=recorder.emit,
        on_state=recorder.on_state,
        **kwargs,  # type: ignore[arg-type]
    )


async def run_for(manager: ManagedSttSession, seconds: float) -> None:
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    task = asyncio.create_task(manager.run(queue))
    for _ in range(3):
        await queue.put(CHUNK)
    await asyncio.sleep(seconds)
    await queue.put(None)
    await asyncio.wait_for(task, 3)


async def test_go_away_rotates_before_break_and_drains_the_late_final() -> None:
    first = ScriptedSttSession(
        [
            (0.01, SttEvent.interim("we")),
            (0.01, SttEvent.final("First sentence.")),
            (0.01, SttEvent.go_away(5.0)),
            (0.08, SttEvent.final("Late final from the old session.")),
        ],
        session_id="s1",
    )
    second = ScriptedSttSession(
        [(0.02, SttEvent.final("Second sentence."))], hold_open=True, session_id="s2"
    )
    recorder = Recorder()
    manager = managed(ScriptedSttEngine([first, second]), recorder)
    await run_for(manager, 0.5)

    finals = [(s.seq, s.text) for s in recorder.segments if s.is_final]
    assert [t for _, t in finals] == [
        "First sentence.",
        "Second sentence.",
        "Late final from the old session.",
    ]
    assert [seq for seq, _ in finals] == [0, 1, 2]  # seq keeps increasing across sessions
    assert [s.seq for s in recorder.segments if not s.is_final] == [0]
    states = [s for s, _ in recorder.states]
    assert states == [
        StageState.STARTING,
        StageState.LIVE,
        StageState.ROTATING,
        StageState.LIVE,
        StageState.STOPPED,
    ]
    assert "GoAway" in (recorder.states[2][1] or "")
    assert manager.stats.rotations == 1 and manager.stats.errors == 0
    assert first.ended is True and first.closed is True  # drained, then closed
    assert second.ended is True and second.closed is True  # source end flushed and closed
    assert manager.session_id == "s2"
    assert manager.stats.last_rotation_gap_ms is not None
    assert manager.stats.last_rotation_gap_ms >= 0


async def test_dedupe_drops_a_late_duplicate_final() -> None:
    first = ScriptedSttSession(
        [
            (0.01, SttEvent.final("Same text here.")),
            (0.01, SttEvent.go_away(3.0)),
            (0.05, SttEvent.final("Same text, here!")),  # same words, different punctuation
        ]
    )
    second = ScriptedSttSession([(0.02, SttEvent.final("Other."))], hold_open=True)
    recorder = Recorder()
    manager = managed(ScriptedSttEngine([first, second]), recorder)
    await run_for(manager, 0.4)
    finals = [(s.seq, s.text) for s in recorder.segments if s.is_final]
    assert finals == [(0, "Same text here."), (1, "Other.")]
    assert manager.stats.duplicates_dropped == 1
    assert normalize_text("Same text, here!") == normalize_text("Same text here.")


async def test_open_failure_keeps_the_old_session_running() -> None:
    first = ScriptedSttSession(
        [
            (0.01, SttEvent.final("Before rotation.")),
            (0.01, SttEvent.go_away(9.0)),
            (0.05, SttEvent.final("Still transcribing while retrying.")),
        ],
        hold_open=True,
        session_id="old",
    )
    second = ScriptedSttSession(
        [(0.01, SttEvent.final("After."))], hold_open=True, session_id="new"
    )
    engine = ScriptedSttEngine([first, RuntimeError("busy"), RuntimeError("busy"), second])
    recorder = Recorder()
    manager = managed(engine, recorder, rng=lambda: 0.0)
    await run_for(manager, 0.5)

    finals = [s for s in recorder.segments if s.is_final]
    texts = [s.text for s in finals]
    assert texts[0] == "Before rotation."
    assert sorted(texts) == sorted(
        ["Before rotation.", "Still transcribing while retrying.", "After."]
    )
    assert [s.seq for s in finals] == [0, 1, 2]
    details = [d for s, d in recorder.states if s is StageState.ROTATING]
    assert any("next session failed: busy" in (d or "") for d in details)
    assert manager.stats.rotations == 1 and manager.stats.errors == 2
    assert manager.session_id == "new"
    assert first.closed is True and second.closed is True


async def test_rotation_postponed_when_every_attempt_fails() -> None:
    first = ScriptedSttSession(
        [(0.01, SttEvent.go_away(9.0)), (0.05, SttEvent.final("Old still works."))],
        hold_open=True,
    )
    engine = ScriptedSttEngine([first, RuntimeError("x"), RuntimeError("x"), RuntimeError("x")])
    recorder = Recorder()
    manager = managed(engine, recorder, max_reconnects=2)
    await run_for(manager, 0.4)
    assert [s.text for s in recorder.segments if s.is_final] == ["Old still works."]
    assert any("rotation postponed" in (d or "") for _, d in recorder.states)
    assert manager.stats.rotations == 0 and manager.stats.errors == 3
    assert recorder.states[-1][0] is StageState.STOPPED  # source ended normally


async def test_server_close_without_go_away_reopens() -> None:
    first = ScriptedSttSession([(0.01, SttEvent.final("One."))])  # script ends → server closed
    second = ScriptedSttSession([(0.01, SttEvent.final("Two."))], hold_open=True)
    recorder = Recorder()
    manager = managed(ScriptedSttEngine([first, second]), recorder)
    await run_for(manager, 0.3)
    assert [s.text for s in recorder.segments if s.is_final] == ["One.", "Two."]
    assert manager.stats.rotations == 1
    assert any("session closed by server" in (d or "") for _, d in recorder.states)


def loud_chunk(amplitude: int = 3000) -> bytes:
    import math
    import struct

    return b"".join(
        struct.pack("<h", int(amplitude * math.sin(2 * math.pi * 440 * i / 16000)))
        for i in range(1600)
    )


async def test_hybrid_vad_swaps_at_the_next_pause() -> None:
    first = ScriptedSttSession([(0.01, SttEvent.go_away(9.0))], hold_open=True, session_id="s1")
    second = ScriptedSttSession([], hold_open=True, session_id="s2")
    recorder = Recorder()
    manager = managed(
        ScriptedSttEngine([first, second]),
        recorder,
        vad_silence_ms=300,
        vad_threshold=300,
        swap_max_wait=5.0,
    )
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    task = asyncio.create_task(manager.run(queue))
    await queue.put(loud_chunk())
    await asyncio.sleep(0.05)  # GoAway arrived: next session opened, but the speaker is talking
    assert manager.session_id == "s1" and manager.state is StageState.ROTATING
    assert "switching at the next pause" in (recorder.states[-1][1] or "")
    for _ in range(3):
        await queue.put(loud_chunk())
    await asyncio.sleep(0.02)
    assert manager.session_id == "s1"  # still speech: no swap yet
    for _ in range(3):  # 300 ms of silence → pause → swap
        await queue.put(CHUNK)
    await asyncio.sleep(0.05)
    assert manager.session_id == "s2" and manager.state is StageState.LIVE
    assert manager.stats.rotations == 1
    assert first.ended is True  # audio_stream_end before the switch (turn finalized)
    await queue.put(None)
    await asyncio.wait_for(task, 3)
    assert first.closed is True and second.closed is True


async def test_swap_watchdog_switches_without_a_pause() -> None:
    first = ScriptedSttSession([(0.01, SttEvent.go_away(9.0))], hold_open=True, session_id="s1")
    second = ScriptedSttSession([], hold_open=True, session_id="s2")
    recorder = Recorder()
    manager = managed(
        ScriptedSttEngine([first, second]), recorder, vad_silence_ms=300, swap_max_wait=0.15
    )
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    task = asyncio.create_task(manager.run(queue))
    for _ in range(40):  # continuous speech
        await queue.put(loud_chunk())
    await asyncio.sleep(0.05)
    assert manager.session_id == "s1"
    await asyncio.sleep(0.2)
    assert manager.session_id == "s2" and manager.stats.rotations == 1
    await queue.put(None)
    await asyncio.wait_for(task, 3)
