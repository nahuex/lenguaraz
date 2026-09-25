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
    for _ in range(100):  # wait for the rotation and the second session's final
        await asyncio.sleep(0.02)
        if recorder.segments:
            break
    await queue.put(None)
    await asyncio.wait_for(task, 2)
    assert manager.stats.rotations >= 1
    assert any("rotation timer" in (d or "") for _, d in recorder.states)
    assert first.closed is True
    assert [s.text for s in recorder.segments] == ["after timer"]


async def test_latency_is_update_gap_for_interims_and_commit_delay_for_finals() -> None:
    session = ScriptedSttSession(
        [
            (0.0, SttEvent.interim("we")),
            (0.10, SttEvent.interim("we are")),
            (0.15, SttEvent.final("We are here.")),
            (0.05, SttEvent.final("No partial before me.")),
        ],
        hold_open=True,
    )
    recorder = Recorder()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    manager = managed(ScriptedSttEngine([session]), recorder)
    task = asyncio.create_task(manager.run(queue))
    await asyncio.sleep(0.45)
    await queue.put(None)
    await asyncio.wait_for(task, 2)
    first, second, final, lonely = recorder.segments
    assert first.latency_ms == 0  # first partial of the utterance
    assert 60 <= second.latency_ms <= 250  # ~100 ms since the previous partial
    assert 100 <= final.latency_ms <= 300  # ~150 ms commit delay after the last partial
    assert lonely.latency_ms == 0  # a final with no partial has no commit delay to report


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


LOUD = (10000).to_bytes(2, "little", signed=True) * 1600  # 3,200 bytes well above the RMS threshold


async def wait_until(predicate, timeout: float = 2.0) -> None:  # type: ignore[no-untyped-def]
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.01)


async def test_stall_watchdog_reopens_a_silent_session() -> None:
    """Spec 007 AC-5: speech flows, the server sends nothing → one stall, one new session."""
    silent = ScriptedSttSession([], hold_open=True, session_id="silent")
    fresh = ScriptedSttSession(
        [(0.01, SttEvent.final("Recovered."))], hold_open=True, session_id="fresh"
    )
    recorder = Recorder()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    manager = managed(ScriptedSttEngine([silent, fresh]), recorder, stall_seconds=0.3)
    task = asyncio.create_task(manager.run(queue))

    async def speak() -> None:
        while manager.stats.stalls == 0:
            await queue.put(LOUD)
            await asyncio.sleep(0.01)

    speaker = asyncio.create_task(speak())
    await wait_until(lambda: manager.stats.stalls == 1)
    await speaker
    await wait_until(lambda: any(s.is_final and s.text == "Recovered." for s in recorder.segments))
    await queue.put(None)
    await asyncio.wait_for(task, 2)

    assert manager.stats.sessions_opened == 2
    assert silent.closed
    assert any(
        state is StageState.ROTATING and "stall" in (detail or "")
        for state, detail in recorder.states
    )
    assert manager.stats.errors == 0  # a stall is not an engine error


async def test_no_stall_without_speech_or_when_disabled() -> None:
    for stall_seconds in (0.2, 0.0):
        session = ScriptedSttSession([], hold_open=True)
        recorder = Recorder()
        queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        manager = managed(ScriptedSttEngine([session]), recorder, stall_seconds=stall_seconds)
        task = asyncio.create_task(manager.run(queue))
        for _ in range(40):
            await queue.put(
                CHUNK if stall_seconds else LOUD
            )  # silence, or speech with the watchdog off
            await asyncio.sleep(0.01)
        await queue.put(None)
        await asyncio.wait_for(task, 2)
        assert manager.stats.stalls == 0 and manager.stats.sessions_opened == 1


async def test_final_is_promoted_from_the_last_interim_when_the_server_never_commits() -> None:
    """A pause was signalled, the server sent interims but no final: after final_timeout the
    last interim becomes the final; a late identical final is de-duplicated."""
    session = ScriptedSttSession(
        [(0.02, SttEvent.interim("Hello")), (0.02, SttEvent.interim("Hello world."))],
        hold_open=True,
    )
    recorder = Recorder()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    manager = managed(
        ScriptedSttEngine([session]),
        recorder,
        vad_silence_ms=40,
        final_timeout=0.2,
        stall_seconds=0,
    )
    task = asyncio.create_task(manager.run(queue))
    await asyncio.sleep(0.1)  # interims arrive
    for _ in range(3):
        await queue.put(LOUD)
    for _ in range(3):
        await queue.put(CHUNK)  # 3 x 100 ms of silence -> audio_stream_end
    await wait_until(lambda: any(s.is_final for s in recorder.segments), timeout=2.0)
    finals = [s for s in recorder.segments if s.is_final]
    assert [f.text for f in finals] == ["Hello world."]
    assert manager.stats.promoted_finals == 1 and manager.stats.finals == 1
    await queue.put(None)
    await asyncio.wait_for(task, 2)


async def test_no_promotion_when_the_real_final_arrives_in_time() -> None:
    session = ScriptedSttSession(
        [(0.02, SttEvent.interim("Hi there")), (0.15, SttEvent.final("Hi there."))],
        hold_open=True,
    )
    recorder = Recorder()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    manager = managed(
        ScriptedSttEngine([session]),
        recorder,
        vad_silence_ms=40,
        final_timeout=0.5,
        stall_seconds=0,
    )
    task = asyncio.create_task(manager.run(queue))
    await asyncio.sleep(0.05)
    for _ in range(3):
        await queue.put(LOUD)
    for _ in range(3):
        await queue.put(CHUNK)
    await wait_until(lambda: any(s.is_final for s in recorder.segments), timeout=2.0)
    await asyncio.sleep(0.6)
    finals = [s for s in recorder.segments if s.is_final]
    assert [f.text for f in finals] == ["Hi there."]
    assert manager.stats.promoted_finals == 0
    await queue.put(None)
    await asyncio.wait_for(task, 2)


async def test_cumulative_interims_promote_only_the_new_sentence() -> None:
    """Server mode seen on 2026-09-25: partials accumulate the whole transcript and no final
    ever comes. Each promotion must emit only the new sentence, and the audience interim must
    show only the current sentence."""
    session = ScriptedSttSession(
        [
            (0.02, SttEvent.interim("Good morning everyone.")),
            (0.30, SttEvent.interim("Good morning everyone.Today we talk")),
            (0.02, SttEvent.interim("Good morning everyone.Today we talk about eBPF.")),
        ],
        hold_open=True,
    )
    recorder = Recorder()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    manager = managed(
        ScriptedSttEngine([session]),
        recorder,
        vad_silence_ms=40,
        final_timeout=0.15,
        stall_seconds=0,
    )
    task = asyncio.create_task(manager.run(queue))
    await asyncio.sleep(0.08)
    for _ in range(2):
        await queue.put(LOUD)
    for _ in range(3):
        await queue.put(CHUNK)  # pause 1
    await wait_until(lambda: sum(s.is_final for s in recorder.segments) == 1, timeout=2.0)
    await asyncio.sleep(0.35)  # second sentence's interims arrive
    for _ in range(2):
        await queue.put(LOUD)
    for _ in range(3):
        await queue.put(CHUNK)  # pause 2
    await wait_until(lambda: sum(s.is_final for s in recorder.segments) == 2, timeout=2.0)
    finals = [s.text for s in recorder.segments if s.is_final]
    assert finals == ["Good morning everyone.", "Today we talk about eBPF."]
    interims = [s.text for s in recorder.segments if not s.is_final]
    assert "Today we talk" in interims and "Good morning everyone.Today we talk" not in interims
    assert manager.stats.promoted_finals + manager.stats.segmented_finals == 2
    await queue.put(None)
    await asyncio.wait_for(task, 2)


async def test_promotion_commits_words_heard_after_the_pause() -> None:
    session = ScriptedSttSession(
        [
            (0.02, SttEvent.interim("Hoy vamos a construir")),
            (0.25, SttEvent.interim("Hoy vamos a construir un servicio")),
        ],
        hold_open=True,
    )
    recorder = Recorder()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    manager = managed(
        ScriptedSttEngine([session]),
        recorder,
        vad_silence_ms=40,
        final_timeout=0.4,
        stall_seconds=0,
    )
    task = asyncio.create_task(manager.run(queue))
    await asyncio.sleep(0.08)
    for _ in range(2):
        await queue.put(LOUD)
    for _ in range(3):
        await queue.put(
            CHUNK
        )  # pause -> audio_stream_end with the snapshot 'Hoy vamos a construir'
    await wait_until(lambda: any(s.is_final for s in recorder.segments), timeout=2.0)
    finals = [s.text for s in recorder.segments if s.is_final]
    assert finals == ["Hoy vamos a construir un servicio"]
    await queue.put(None)
    await asyncio.wait_for(task, 2)


async def test_sentences_are_closed_at_punctuation_without_duplicates() -> None:
    """Cumulative partials with revisions (a comma is inserted into committed text): each
    sentence becomes a final as soon as the next one starts, and nothing is repeated."""
    session = ScriptedSttSession(
        [
            (0.02, SttEvent.interim("Buenas tardes a todos y gracias")),
            (0.02, SttEvent.interim("Buenas tardes a todos y gracias por venir. Hoy vamos")),
            (
                0.02,
                SttEvent.interim(
                    "Buenas tardes a todos, y gracias por venir. Hoy vamos a construir."
                ),
            ),
            (
                0.02,
                SttEvent.interim(
                    "Buenas tardes a todos, y gracias por venir. "
                    "Hoy vamos a construir. \u00bfListos"
                ),
            ),
        ],
        hold_open=True,
    )
    recorder = Recorder()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    manager = managed(ScriptedSttEngine([session]), recorder, stall_seconds=0, final_timeout=0)
    task = asyncio.create_task(manager.run(queue))
    await wait_until(lambda: sum(s.is_final for s in recorder.segments) == 2, timeout=2.0)
    finals = [s.text for s in recorder.segments if s.is_final]
    assert finals == ["Buenas tardes a todos y gracias por venir.", "Hoy vamos a construir."]
    later = [
        s.text
        for s in recorder.segments[
            recorder.segments.index(next(s for s in recorder.segments if s.is_final)) + 1 :
        ]
    ]
    assert not any("Buenas" in text for text in later)  # never repeated
    assert manager.stats.segmented_finals == 2
    await queue.put(None)
    await asyncio.wait_for(task, 2)


def test_long_run_on_partial_is_cut_at_a_clause_or_word_cap() -> None:
    from lenguaraz.stt.session import segment_cut

    words = " ".join(f"palabra{i}" for i in range(30))
    cut = segment_cut(words)
    assert cut is not None and len(words[:cut].split()) == 20
    with_comma = "uno dos tres cuatro cinco seis siete ocho nueve, " + words
    cut = segment_cut(with_comma)
    assert with_comma[:cut].endswith("nueve,")
    assert segment_cut("una frase corta sin punto") is None
    assert segment_cut("Node.js y v1.2 no cortan") is None


def test_committed_offset_tolerates_revisions() -> None:
    from lenguaraz.stt.session import committed_offset

    committed = "Cada escenario tiene su propio task group y su propia cola con back pressure."
    text = (
        "Cada escenario tiene su propio TaskGroup y su propia cola con backpressure. "
        "Para transcribir"
    )
    offset = committed_offset(text, committed)
    assert offset is not None and text[offset:].strip(" .") == "Para transcribir"
    assert committed_offset("Otra cosa distinta", committed) is None
