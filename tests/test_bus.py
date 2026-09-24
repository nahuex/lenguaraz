# SPDX-License-Identifier: Apache-2.0
"""Spec 001 — FR-001-07, AC-7 (backpressure never drops finals)."""

from __future__ import annotations

import asyncio

import pytest

from lenguaraz.bus.memory import MemoryBus, SlowConsumerError
from lenguaraz.models import CaptionEvent, MetricsEvent, StageState, StatusEvent, parse_event


def caption(seq: int, *, final: bool, lang: str = "en") -> CaptionEvent:
    return CaptionEvent(
        stage_id="main",
        seq=seq,
        lang=lang,
        source_lang="en",
        is_final=final,
        text=f"{'final' if final else 'interim'} {seq}",
        t_audio_ms=seq * 1000,
        latency_ms=100,
    )


async def drain(sub, n: int) -> list:  # type: ignore[no-untyped-def]
    return [await sub.get() for _ in range(n)]


async def test_publish_delivers_to_every_subscriber() -> None:
    bus = MemoryBus()
    a = bus.subscribe("main")
    b = bus.subscribe("main")
    other = bus.subscribe("other")
    bus.publish("main", caption(1, final=True))
    assert (await a.get()).seq == 1
    assert (await b.get()).seq == 1
    assert bus.listeners("main") == 2
    assert bus.listeners("other") == 1
    other.close()
    assert bus.listeners("other") == 0


async def test_full_queue_drops_oldest_interim_and_keeps_finals() -> None:
    bus = MemoryBus(queue_size=4)
    sub = bus.subscribe("main")
    for seq in range(1, 5):
        bus.publish("main", caption(seq, final=False))  # queue full: i1 i2 i3 i4
    bus.publish("main", caption(4, final=True))  # evicts i1 → i2 i3 i4 f4
    for seq in range(5, 8):
        bus.publish("main", caption(seq, final=False))  # evicts i2 i3 i4 → f4 i5 i6 i7
    received = await drain(sub, 4)
    assert [(e.seq, e.is_final) for e in received] == [
        (4, True),
        (5, False),
        (6, False),
        (7, False),
    ]
    assert sub.dropped == 4


async def test_incoming_interim_is_dropped_when_only_finals_are_queued() -> None:
    bus = MemoryBus(queue_size=2)
    sub = bus.subscribe("main")
    bus.publish("main", caption(1, final=True))
    bus.publish("main", caption(2, final=True))
    bus.publish("main", caption(3, final=False))  # nothing droppable: the interim is skipped
    assert sub.dropped == 1
    received = await drain(sub, 2)
    assert [e.seq for e in received] == [1, 2]


async def test_slow_consumer_is_closed_instead_of_losing_a_final() -> None:
    bus = MemoryBus(queue_size=2)
    sub = bus.subscribe("main")
    bus.publish("main", caption(1, final=True))
    bus.publish("main", caption(2, final=True))
    bus.publish("main", caption(3, final=True))  # would lose a final → subscription closed
    assert bus.listeners("main") == 0
    assert (await sub.get()).seq == 1
    assert (await sub.get()).seq == 2
    with pytest.raises(SlowConsumerError):
        await sub.get()


async def test_status_and_metrics_bypass_the_language_filter() -> None:
    bus = MemoryBus()
    es = bus.subscribe("main", lang="es")
    bus.publish("main", caption(1, final=True, lang="en"))
    bus.publish("main", StatusEvent(stage_id="main", state=StageState.LIVE))
    bus.publish("main", caption(1, final=True, lang="es"))
    bus.publish("main", MetricsEvent(stage_id="main", p50_ms=1, p95_ms=2, rotations=0, errors=0))
    received = await drain(es, 3)
    assert [type(e).__name__ for e in received] == ["StatusEvent", "CaptionEvent", "MetricsEvent"]
    assert received[1].lang == "es"  # type: ignore[union-attr]
    assert bus.languages_with_listeners("main") == {"es"}
    assert bus.listeners("main", lang="es") == 1
    assert bus.listeners("main", lang="pt") == 0


async def test_get_waits_for_the_next_event_and_close_ends_iteration() -> None:
    bus = MemoryBus()
    sub = bus.subscribe("main")

    async def publish_later() -> None:
        await asyncio.sleep(0.01)
        bus.publish("main", caption(9, final=True))
        await asyncio.sleep(0.01)
        sub.close()

    asyncio.get_running_loop().create_task(publish_later())
    received = [event async for event in sub]
    assert [e.seq for e in received] == [9]  # type: ignore[union-attr]


def test_events_round_trip_through_json() -> None:
    event = caption(3, final=False)
    parsed = parse_event(event.model_dump_json())
    assert parsed == event
    assert parse_event('{"type":"status","stage_id":"main","state":"LIVE","detail":null}') == (
        StatusEvent(stage_id="main", state=StageState.LIVE)
    )
