# SPDX-License-Identifier: Apache-2.0
"""Spec 001 — FR-001-05, FR-001-11, AC-8 (two stages isolated), metrics ticker."""

from __future__ import annotations

import asyncio
import time
import wave
from pathlib import Path

from lenguaraz.bus.memory import MemoryBus
from lenguaraz.config import Settings, StageConfig, StagesFile
from lenguaraz.ingest.wav import WavFileSource
from lenguaraz.models import CaptionEvent, MetricsEvent, StageState, StatusEvent
from lenguaraz.runner import StageManager, StageRunner
from lenguaraz.stt.fake import FakeSttEngine


def write_wav(path: Path, seconds: float) -> Path:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(bytes(int(16000 * seconds) * 2))
    return path


SPEEDUP = 20.0  # virtual clock: 3 s of audio streams in 150 ms of wall time


def fast_source(source: str, **_: object) -> WavFileSource:
    return WavFileSource(
        source,
        realtime=True,
        loop=True,
        sleep=lambda s: asyncio.sleep(s / SPEEDUP),
        clock=lambda: time.monotonic() * SPEEDUP,
    )


def settings() -> Settings:
    return Settings(_env_file=None, engine="fake")


def make_stages(tmp_path: Path) -> StagesFile:
    wav = write_wav(tmp_path / "talk.wav", 3.0)
    (tmp_path / "talk.txt").write_text("Alpha beta gamma.\nDelta epsilon.\n", encoding="utf-8")
    return StagesFile(
        stages=[
            StageConfig(id="main", name="Main", source=str(wav), source_lang=["en-US"]),
            StageConfig(id="side", name="Side", source=str(wav), source_lang=["es-419"]),
        ]
    )


async def drain(sub, seconds: float) -> list:  # type: ignore[no-untyped-def]
    events = []
    deadline = asyncio.get_running_loop().time() + seconds
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            return events
        try:
            events.append(await asyncio.wait_for(sub.get(), remaining))
        except TimeoutError:
            return events


async def test_two_stages_run_independently_and_one_can_stop(tmp_path: Path) -> None:
    bus = MemoryBus()
    manager = StageManager(
        make_stages(tmp_path),
        engine=FakeSttEngine(words_per_second=10),
        bus=bus,
        settings=settings(),
        source_factory=fast_source,
        metrics_interval=0.05,
    )
    main_sub = bus.subscribe("main", lang="en")
    side_sub = bus.subscribe("side", lang="es")
    await manager.start_all()
    main_events, side_events = await asyncio.gather(drain(main_sub, 0.4), drain(side_sub, 0.4))

    for events, lang in ((main_events, "en"), (side_events, "es")):
        captions = [e for e in events if isinstance(e, CaptionEvent)]
        assert captions, "expected captions from the fake engine"
        assert {c.lang for c in captions} == {lang}
        assert any(c.is_final for c in captions)
        assert all(c.latency_ms >= 0 and c.t_audio_ms >= 0 for c in captions)
        assert any(isinstance(e, MetricsEvent) for e in events)
        statuses = [e.state for e in events if isinstance(e, StatusEvent)]
        assert statuses[:2] == [StageState.STARTING, StageState.LIVE]

    snapshot = {row["id"]: row for row in manager.snapshot()}
    assert snapshot["main"]["state"] == "LIVE" and snapshot["side"]["state"] == "LIVE"
    assert snapshot["main"]["dry_run"] is True
    assert snapshot["main"]["listeners"] == 1
    assert snapshot["main"]["captions_final"] >= 1

    side = manager.get("side")
    assert side is not None
    await side.stop()
    assert side.state is StageState.STOPPED and side.running is False
    assert manager.get("main").state is StageState.LIVE  # type: ignore[union-attr]
    later = await drain(main_sub, 0.15)
    assert any(isinstance(e, CaptionEvent) for e in later)
    await manager.stop_all()
    assert all(r.state is StageState.STOPPED for r in manager.runners.values())


async def test_bad_source_stops_only_that_stage_with_a_reason(tmp_path: Path) -> None:
    bus = MemoryBus()
    stage = StageConfig(id="broken", name="Broken", source=str(tmp_path / "missing.wav"))
    runner = StageRunner(
        stage,
        engine=FakeSttEngine(),
        bus=bus,
        settings=settings(),
        source_factory=lambda source, **_: WavFileSource(source, realtime=False),
        metrics_interval=1.0,
    )
    sub = bus.subscribe("broken")
    await runner.start()
    events = await drain(sub, 0.3)
    statuses = [(e.state, e.detail) for e in events if isinstance(e, StatusEvent)]
    assert statuses[-1][0] is StageState.STOPPED
    assert "cannot open WAV" in (statuses[-1][1] or "")
    assert runner.running is False
    await runner.stop()


async def test_source_factory_failure_is_reported(tmp_path: Path) -> None:
    def exploding(source: str, **_: object) -> WavFileSource:
        raise RuntimeError("device busy")

    bus = MemoryBus()
    runner = StageRunner(
        StageConfig(id="cam", name="Cam", source="device:0"),
        engine=FakeSttEngine(),
        bus=bus,
        settings=settings(),
        source_factory=exploding,
    )
    sub = bus.subscribe("cam")
    await runner.start()
    events = await drain(sub, 0.2)
    assert any(
        isinstance(e, StatusEvent)
        and e.state is StageState.STOPPED
        and "device busy" in (e.detail or "")
        for e in events
    )


class SlowOpenEngine:
    """Wraps the fake engine with a connect delay, like a real Live handshake."""

    name = "slow"

    def __init__(self, delay: float) -> None:
        self._inner = FakeSttEngine(words_per_second=10)
        self._delay = delay

    async def open(self, stage: StageConfig):  # type: ignore[no-untyped-def]
        await asyncio.sleep(self._delay)
        return await self._inner.open(stage)


class FloodSource:
    """A live stream that produces audio faster than real time and never ends."""

    def __init__(self, chunks: int) -> None:
        self._chunks = chunks
        self.closed = False
        self._stop = asyncio.Event()

    async def chunks(self):  # type: ignore[no-untyped-def]
        for _ in range(self._chunks):
            yield bytes(3200)
            await asyncio.sleep(0)
        await self._stop.wait()

    async def close(self) -> None:
        self.closed = True
        self._stop.set()


async def test_file_source_waits_for_live(tmp_path: Path) -> None:
    """Spec 003 AC-4: nothing is replayed before the session is connected."""
    bus = MemoryBus()
    wav = write_wav(tmp_path / "talk.wav", 2.0)
    runner = StageRunner(
        StageConfig(id="f", name="F", source=str(wav), source_lang=["en-US"]),
        engine=SlowOpenEngine(0.3),  # type: ignore[arg-type]
        bus=bus,
        settings=settings(),
        source_factory=fast_source,
        metrics_interval=1.0,
    )
    await runner.start()
    await asyncio.sleep(0.15)
    assert runner.state is StageState.STARTING
    assert runner.session is not None and runner.session.stats.bytes_sent == 0
    await asyncio.sleep(0.4)
    assert runner.state is StageState.LIVE
    assert runner.session.stats.bytes_sent > 0
    await runner.stop()


async def test_live_source_drops_oldest_when_the_queue_is_full() -> None:
    """Spec 003 AC-5: a stream never blocks; the backlog is bounded and counted."""
    bus = MemoryBus()
    flood = FloodSource(chunks=300)
    runner = StageRunner(
        StageConfig(id="s", name="S", source="srt://10.0.0.5:9000", source_lang=["en-US"]),
        engine=SlowOpenEngine(0.3),  # type: ignore[arg-type]
        bus=bus,
        settings=settings(),
        source_factory=lambda source, **_: flood,
        metrics_interval=1.0,
    )
    await runner.start()
    await asyncio.sleep(0.2)
    assert runner.chunks_dropped >= 200  # 300 chunks flooded into a 50-chunk queue
    assert runner.snapshot()["chunks_dropped"] == runner.chunks_dropped
    await asyncio.sleep(0.3)
    assert runner.state is StageState.LIVE
    await runner.stop()
    assert flood.closed is True
