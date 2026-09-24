# SPDX-License-Identifier: Apache-2.0
"""Spec 002 — FR-002-06, AC-5: progressive translation of a debounced partial hypothesis."""

from __future__ import annotations

import asyncio

from lenguaraz.bus.memory import MemoryBus
from lenguaraz.config import Settings, StageConfig
from lenguaraz.models import CaptionEvent
from lenguaraz.translate.fake import FakeTranslator
from lenguaraz.translate.fanout import TranslationFanout

STAGE = StageConfig(id="main", name="M", source="x.wav", source_lang=["en-US"], targets=["es"])


def caption(seq: int, text: str, *, final: bool) -> CaptionEvent:
    return CaptionEvent(
        stage_id="main",
        seq=seq,
        lang="en",
        source_lang="en",
        is_final=final,
        text=text,
        t_audio_ms=0,
        latency_ms=0,
    )


async def collect(sub, seconds: float) -> list[CaptionEvent]:  # type: ignore[no-untyped-def]
    out: list[CaptionEvent] = []
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    while (remaining := deadline - loop.time()) > 0:
        try:
            event = await asyncio.wait_for(sub.get(), remaining)
        except TimeoutError:
            break
        if isinstance(event, CaptionEvent):
            out.append(event)
    return out


async def test_stable_prefix_is_translated_as_interim_then_replaced_by_the_final() -> None:
    now = [100.0]
    bus = MemoryBus()
    translator = FakeTranslator()
    settings = Settings(
        _env_file=None, engine="fake", always_on_langs="es", progressive_translation=True
    )
    fanout = TranslationFanout(STAGE, translator, bus, settings, clock=lambda: now[0])
    es = bus.subscribe("main", lang="es")

    fanout.on_caption(caption(0, "we are going", final=False))  # 3 words < 6 → nothing
    await asyncio.sleep(0.02)
    assert translator.requests == []

    fanout.on_caption(caption(0, "we are going to talk about eBPF today, and", final=False))
    await asyncio.sleep(0.02)
    now[0] += 0.1
    fanout.on_caption(caption(0, "we are going to talk about eBPF today, and then", final=False))
    await asyncio.sleep(0.02)  # within the 600 ms debounce → ignored
    assert len(translator.requests) == 1

    now[0] += 1.0
    fanout.on_caption(
        caption(0, "We are going to talk about eBPF today, and then we stop.", final=True)
    )
    events = await collect(es, 0.2)
    assert [(e.seq, e.is_final, e.text) for e in events] == [
        (0, False, "[es] we are going to talk about eBPF today, and"),
        (0, True, "[es] We are going to talk about eBPF today, and then we stop."),
    ]
    assert events[0].original == "we are going to talk about eBPF today, and"
    await fanout.stop()


async def test_flag_off_disables_progressive_translation() -> None:
    bus = MemoryBus()
    translator = FakeTranslator()
    settings = Settings(
        _env_file=None, engine="fake", always_on_langs="es", progressive_translation=False
    )
    fanout = TranslationFanout(STAGE, translator, bus, settings)
    fanout.on_caption(caption(0, "we are going to talk about eBPF today, and more", final=False))
    await asyncio.sleep(0.02)
    assert translator.requests == []
    await fanout.stop()
