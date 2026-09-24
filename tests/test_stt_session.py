# SPDX-License-Identifier: Apache-2.0
"""Spec 001 — FR-001-03/04/06, AC-4 (interim/final seq), AC-5 (reconnect, GoAway, no lost final)."""

from __future__ import annotations

import asyncio

from lenguaraz.config import StageConfig
from lenguaraz.models import StageState
from lenguaraz.stt.base import SttEvent
from lenguaraz.stt.fake import (
    DEMO_SENTENCES,
    FakeSttEngine,
    FakeSttSession,
    ScriptedSttEngine,
    ScriptedSttSession,
)
from lenguaraz.stt.session import ManagedSttSession, Segment

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


def managed(engine, recorder: Recorder, **kwargs):  # type: ignore[no-untyped-def]
    kwargs.setdefault("sleep", fast_sleep)
    kwargs.setdefault("rotate_seconds", 1000.0)
    kwargs.setdefault("drain_seconds", 0.05)
    return ManagedSttSession(
        STAGE, engine, emit=recorder.emit, on_state=recorder.on_state, **kwargs
    )


async def feed(queue: asyncio.Queue[bytes | None], n: int, *, end: bool = True) -> None:
    for _ in range(n):
        await queue.put(CHUNK)
    if end:
        await queue.put(None)


async def test_interims_and_final_share_one_seq() -> None:
    session = ScriptedSttSession(
        [
            (0.01, SttEvent.interim("hel")),
            (0.01, SttEvent.interim("hello wor")),
            (0.01, SttEvent.final("Hello world.")),
            (0.01, SttEvent.interim("second")),
            (0.01, SttEvent.final("Second sentence.")),
            (0.01, SttEvent.final("   ")),  # blank finals are ignored
        ],
        hold_open=True,
    )
    recorder = Recorder()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    manager = managed(ScriptedSttEngine([session]), recorder)
    await feed(queue, 5, end=False)
    task = asyncio.create_task(manager.run(queue))
    await asyncio.sleep(0.15)
    await queue.put(None)
    await asyncio.wait_for(task, 2)

    assert [(s.seq, s.is_final, s.text) for s in recorder.segments] == [
        (0, False, "hel"),
        (0, False, "hello wor"),
        (0, True, "Hello world."),
        (1, False, "second"),
        (1, True, "Second sentence."),
    ]
    assert all(s.latency_ms >= 0 for s in recorder.segments)
    assert recorder.segments[-1].t_audio_ms == 500  # five 100 ms chunks
    assert len(session.sent) == 5 * 3200
    assert session.ended is True and session.closed is True
    assert [s for s, _ in recorder.states] == [
        StageState.STARTING,
        StageState.LIVE,
        StageState.STOPPED,
    ]
    assert recorder.states[-1][1] == "source ended"
    assert manager.stats.finals == 2 and manager.stats.interims == 3


async def test_connect_failure_then_go_away_then_recovery_loses_no_final() -> None:
    first = ScriptedSttSession(
        [(0.01, SttEvent.interim("we are")), (0.01, SttEvent.go_away(5.0))], session_id="s1"
    )
    second = ScriptedSttSession(
        [(0.01, SttEvent.final("We are back."))], hold_open=True, session_id="s2"
    )
    engine = ScriptedSttEngine([ConnectionError("dns"), first, second])
    recorder = Recorder()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    manager = managed(engine, recorder, rng=lambda: 0.0)
    await feed(queue, 3, end=False)
    task = asyncio.create_task(manager.run(queue))
    await asyncio.sleep(0.2)
    await queue.put(None)
    await asyncio.wait_for(task, 2)

    states = [s for s, _ in recorder.states]
    assert states == [
        StageState.STARTING,
        StageState.DEGRADED,
        StageState.LIVE,
        StageState.ROTATING,
        StageState.LIVE,
        StageState.STOPPED,
    ]
    assert "connect failed: dns" in (recorder.states[1][1] or "")
    assert "GoAway" in (recorder.states[3][1] or "")
    assert [(s.seq, s.is_final, s.text) for s in recorder.segments] == [
        (0, False, "we are"),
        (0, True, "We are back."),
    ]
    assert manager.stats.rotations == 1 and manager.stats.errors == 1
    assert manager.stats.sessions_opened == 2
    assert manager.session_id == "s2"


async def test_gives_up_after_max_reconnects() -> None:
    engine = ScriptedSttEngine([RuntimeError("boom")] * 3)
    recorder = Recorder()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    manager = managed(engine, recorder, max_reconnects=2)
    await asyncio.wait_for(manager.run(queue), 2)
    states = [s for s, _ in recorder.states]
    assert states == [
        StageState.STARTING,
        StageState.DEGRADED,
        StageState.DEGRADED,
        StageState.STOPPED,
    ]
    assert "gave up after 2 reconnects" in (recorder.states[-1][1] or "")
    assert manager.stats.errors == 3


async def test_non_retryable_error_stops_the_stage() -> None:
    session = ScriptedSttSession([SttEvent.failure("API key not valid", code=400, retryable=False)])
    recorder = Recorder()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    manager = managed(ScriptedSttEngine([session]), recorder)
    await asyncio.wait_for(manager.run(queue), 2)
    assert recorder.states[-1] == (StageState.STOPPED, "API key not valid")


async def test_retryable_error_reconnects() -> None:
    first = ScriptedSttSession([(0.01, SttEvent.failure("503 unavailable", code=503))])
    second = ScriptedSttSession([(0.01, SttEvent.final("ok"))], hold_open=True)
    recorder = Recorder()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    manager = managed(ScriptedSttEngine([first, second]), recorder)
    task = asyncio.create_task(manager.run(queue))
    await asyncio.sleep(0.1)
    await queue.put(None)
    await asyncio.wait_for(task, 2)
    assert StageState.DEGRADED in [s for s, _ in recorder.states]
    assert [s.text for s in recorder.segments] == ["ok"]


async def test_send_failure_is_a_retryable_error() -> None:
    broken = ScriptedSttSession([], send_error=OSError("socket closed"), hold_open=True)
    good = ScriptedSttSession([(0.01, SttEvent.final("after"))], hold_open=True)
    recorder = Recorder()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    manager = managed(ScriptedSttEngine([broken, good]), recorder)
    await queue.put(CHUNK)
    task = asyncio.create_task(manager.run(queue))
    await asyncio.sleep(0.1)
    await queue.put(None)
    await asyncio.wait_for(task, 2)
    assert any("send failed" in (d or "") for _, d in recorder.states)
    assert [s.text for s in recorder.segments] == ["after"]


async def test_rotation_timer_reopens_the_session() -> None:
    first = ScriptedSttSession([], hold_open=True, session_id="a")
    second = ScriptedSttSession(
        [(0.01, SttEvent.final("after timer"))], hold_open=True, session_id="b"
    )
    recorder = Recorder()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    manager = managed(ScriptedSttEngine([first, second]), recorder, rotate_seconds=0.05)
    task = asyncio.create_task(manager.run(queue))
    await asyncio.sleep(0.08)  # first rotation at 50 ms, final from the second session at 60 ms
    await queue.put(None)
    await asyncio.wait_for(task, 2)
    assert manager.stats.rotations == 1
    assert any("rotation timer" in (d or "") for _, d in recorder.states)
    assert first.closed is True
    assert [s.text for s in recorder.segments] == ["after timer"]


async def test_latency_uses_the_audio_timeline() -> None:
    now = [100.0]
    recorder = Recorder()
    session = ScriptedSttSession([], hold_open=True)
    manager = managed(ScriptedSttEngine([session]), recorder, clock=lambda: now[0])
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    task = asyncio.create_task(manager.run(queue))
    await queue.put(CHUNK)
    await queue.put(CHUNK)
    await asyncio.sleep(0.02)
    now[0] = 100.0 + 0.2 + 0.35  # 200 ms of audio sent, 550 ms elapsed → 350 ms lag
    assert manager.t_audio_ms() == 200
    assert manager.latency_ms() == 350
    await queue.put(None)
    await asyncio.wait_for(task, 2)


async def test_fake_session_paces_on_audio_and_reads_reference_text(tmp_path) -> None:  # type: ignore[no-untyped-def]
    wav = tmp_path / "talk.wav"
    wav.write_bytes(b"")
    (tmp_path / "talk.txt").write_text("# comment\nOne two three.\nFour five.\n", encoding="utf-8")
    stage = StageConfig(id="s", name="S", source=str(wav), source_lang=["es-419"])
    session = await FakeSttEngine(words_per_second=10, loop=False).open(stage)
    assert isinstance(session, FakeSttSession)

    events: list[SttEvent] = []

    async def collect() -> None:
        async for event in session.events():
            events.append(event)

    task = asyncio.create_task(collect())
    await asyncio.sleep(0.01)
    assert events == []  # nothing until audio arrives
    for _ in range(40):  # 4 s of audio
        await session.send(CHUNK)
    await asyncio.sleep(0.05)
    await session.close()
    await asyncio.wait_for(task, 1)
    texts = [(e.kind.value, e.text) for e in events]
    assert texts[:3] == [("interim", "One"), ("interim", "One two"), ("final", "One two three.")]
    assert ("final", "Four five.") in texts
    assert all(e.language_code == "es" for e in events)


async def test_fake_engine_falls_back_to_demo_text_for_streams() -> None:
    stage = StageConfig(id="s", name="S", source="srt://host:9000", source_lang=[])
    session = await FakeSttEngine().open(stage)
    assert session._sentences == DEMO_SENTENCES["en"]
