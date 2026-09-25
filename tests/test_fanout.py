# SPDX-License-Identifier: Apache-2.0
"""Spec 002 — FR-002-03/05/07, AC-3 (fan-out), AC-4 (pass-through), AC-6 (errors)."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from lenguaraz.bus.memory import MemoryBus, MemorySubscription
from lenguaraz.config import Settings, StageConfig
from lenguaraz.models import CaptionEvent
from lenguaraz.translate.base import TranslationError
from lenguaraz.translate.fake import FakeTranslator
from lenguaraz.translate.fanout import TranslationFanout

STAGE = StageConfig(
    id="main",
    name="Main",
    source="x.wav",
    source_lang=["en-US"],
    targets=["es", "pt"],
    glossary=["eBPF", "Kubernetes"],
    talk={"title": "Observability", "abstract": "Kernel tracing."},
)


def settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, engine="fake", always_on_langs="es", **overrides)  # type: ignore[arg-type]


def caption(seq: int, text: str, *, final: bool = True, lang: str = "en") -> CaptionEvent:
    return CaptionEvent(
        stage_id="main",
        seq=seq,
        lang=lang,
        source_lang=lang,
        is_final=final,
        text=text,
        t_audio_ms=seq * 1000,
        latency_ms=0,
    )


async def fast_sleep(seconds: float) -> None:
    await asyncio.sleep(0)


async def drain(sub: MemorySubscription, seconds: float) -> list[CaptionEvent]:
    events: list[CaptionEvent] = []
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            return events
        try:
            event = await asyncio.wait_for(sub.get(), remaining)
        except TimeoutError:
            return events
        if isinstance(event, CaptionEvent):
            events.append(event)


@pytest.fixture
def bus() -> Iterator[MemoryBus]:
    yield MemoryBus()


async def test_finals_fan_out_to_active_languages_with_same_seq(bus: MemoryBus) -> None:
    translator = FakeTranslator()
    fanout = TranslationFanout(STAGE, translator, bus, settings(), sleep=fast_sleep)
    es = bus.subscribe("main", lang="es")
    pt = bus.subscribe("main", lang="pt")  # a pt listener makes pt active
    original = caption(7, "We attach programs to kernel hooks.")
    bus.publish("main", original)
    fanout.on_caption(original)
    es_events, pt_events = await asyncio.gather(drain(es, 0.2), drain(pt, 0.2))
    assert [(e.seq, e.lang, e.text, e.original) for e in es_events] == [
        (7, "es", "[es] We attach programs to kernel hooks.", "We attach programs to kernel hooks.")
    ]
    assert pt_events[0].lang == "pt" and pt_events[0].seq == 7 and pt_events[0].is_final
    assert pt_events[0].source_lang == "en" and pt_events[0].degraded is False
    request = translator.requests[0]
    assert request.glossary == ("eBPF", "Kubernetes") and request.talk_title == "Observability"
    assert set(fanout.usage()) == {"es", "pt"}
    assert fanout.usage()["es"]["calls"] == 1
    await fanout.stop()


async def test_inactive_language_is_not_translated(bus: MemoryBus) -> None:
    translator = FakeTranslator()
    fanout = TranslationFanout(STAGE, translator, bus, settings(), sleep=fast_sleep)
    fanout.on_caption(caption(1, "Hello."))
    await asyncio.sleep(0.05)
    assert [r.target_lang for r in translator.requests] == ["es"]  # always_on only, no pt listener
    await fanout.stop()


async def test_pass_through_never_calls_the_engine_for_the_source_language(bus: MemoryBus) -> None:
    stage = StageConfig(
        id="main", name="M", source="x.wav", source_lang=["en-US"], targets=["en", "es"]
    )
    translator = FakeTranslator()
    fanout = TranslationFanout(stage, translator, bus, settings(), sleep=fast_sleep)
    en = bus.subscribe("main", lang="en")
    original = caption(3, "Plain English.")
    bus.publish("main", original)  # the runner publishes the original first
    fanout.on_caption(original)
    events = await drain(en, 0.1)
    assert [(e.seq, e.text, e.original) for e in events] == [(3, "Plain English.", None)]
    assert all(r.target_lang != "en" for r in translator.requests)
    await fanout.stop()


async def test_order_is_preserved_per_language(bus: MemoryBus) -> None:
    translator = FakeTranslator(delay=0.02)
    # concurrency 1: the context of a request is the previous *finished* translations
    fanout = TranslationFanout(
        STAGE, translator, bus, settings(translate_concurrency=1), sleep=fast_sleep
    )
    es = bus.subscribe("main", lang="es")
    for seq in range(4):
        fanout.on_caption(caption(seq, f"Sentence {seq}."))
    events = await drain(es, 0.5)
    assert [e.seq for e in events] == [0, 1, 2, 3]
    assert translator.requests[2].context == (
        ("Sentence 0.", "[es] Sentence 0."),
        ("Sentence 1.", "[es] Sentence 1."),
    )
    await fanout.stop()


async def test_transient_errors_retry_then_succeed(bus: MemoryBus) -> None:
    translator = FakeTranslator(
        failures=[TranslationError("503", code=503), TranslationError("503", code=503)]
    )
    fanout = TranslationFanout(STAGE, translator, bus, settings(), sleep=fast_sleep)
    es = bus.subscribe("main", lang="es")
    fanout.on_caption(caption(1, "Retry me."))
    events = await drain(es, 0.3)
    assert [(e.text, e.degraded) for e in events] == [("[es] Retry me.", False)]
    assert len(translator.requests) == 3
    await fanout.stop()


async def test_persistent_failure_publishes_degraded_caption_and_status(bus: MemoryBus) -> None:
    details: list[str] = []
    translator = FakeTranslator(failures=[TranslationError("upstream", code=503)] * 5)
    fanout = TranslationFanout(
        STAGE, translator, bus, settings(), sleep=fast_sleep, on_status=details.append
    )
    es = bus.subscribe("main", lang="es")
    fanout.on_caption(caption(1, "No luck."))
    events = await drain(es, 0.3)
    assert events == []  # each language shows only its own language: the sentence is skipped
    assert fanout.untranslated() == 1
    assert details and "translation to es failed" in details[0] and "upstream" in details[0]
    assert len(translator.requests) == 4  # 1 + 3 retries
    await fanout.stop()


async def test_non_retryable_error_degrades_immediately(bus: MemoryBus) -> None:
    translator = FakeTranslator(failures=[TranslationError("bad", code=400, retryable=False)])
    fanout = TranslationFanout(STAGE, translator, bus, settings(), sleep=fast_sleep)
    es = bus.subscribe("main", lang="es")
    fanout.on_caption(caption(1, "Bad request."))
    events = await drain(es, 0.2)
    assert events == [] and len(translator.requests) == 1 and fanout.untranslated() == 1
    await fanout.stop()


async def test_rate_limit_pauses_translation_and_shows_the_original(bus: MemoryBus) -> None:
    """Spec 002 FR-002-14: a 429 pauses the language for the server's hint; no hammering."""
    now = [1000.0]
    details: list[str] = []
    translator = FakeTranslator(
        failures=[
            TranslationError("quota exhausted (429): limit 15. Please retry in 40.5s.", code=429)
        ]
    )
    fanout = TranslationFanout(
        STAGE,
        translator,
        bus,
        settings(),
        sleep=fast_sleep,
        clock=lambda: now[0],
        on_status=details.append,
    )
    es = bus.subscribe("main", lang="es")
    fanout.on_caption(caption(1, "First."))
    events = await drain(es, 0.2)
    assert events == []  # skipped, not shown in Spanish as Spanish-less text
    assert len(translator.requests) == 1  # no retries on 429
    assert details and "rate limited (429)" in details[0] and "40s" in details[0]

    fanout.on_caption(caption(2, "A partial sentence with enough words to translate", final=False))
    fanout.on_caption(caption(3, "Third."))
    events = await drain(es, 0.2)
    assert events == []  # paused: nothing published in this language
    assert len(translator.requests) == 1  # nothing sent while paused
    assert fanout.rate_limited() == 1 and fanout.untranslated() == 2

    now[0] += 41.0
    fanout.on_caption(caption(4, "Fourth."))
    events = await drain(es, 0.2)
    assert [(e.text, e.degraded) for e in events] == [("[es] Fourth.", False)]
    assert len(translator.requests) == 2
    await fanout.stop()


async def test_slow_translation_times_out_and_degrades_without_blocking(bus: MemoryBus) -> None:
    translator = FakeTranslator(delay=5.0)
    fanout = TranslationFanout(
        STAGE, translator, bus, settings(translate_timeout_seconds=0.2), sleep=fast_sleep
    )
    es = bus.subscribe("main", lang="es")
    fanout.on_caption(caption(1, "Slow one."))
    events = await drain(es, 1.0)
    assert events == [] and fanout.untranslated() == 1
    assert len(translator.requests) == 1  # no retries on a timeout
    await fanout.stop()


async def test_finals_translate_concurrently_and_publish_in_order(bus: MemoryBus) -> None:
    translator = FakeTranslator(delay=0.4)
    fanout = TranslationFanout(
        STAGE, translator, bus, settings(translate_concurrency=4), sleep=fast_sleep
    )
    es = bus.subscribe("main", lang="es")
    for seq in range(1, 5):
        fanout.on_caption(caption(seq, f"Sentence {seq}."))
    events = await drain(es, 0.9)  # sequential would need 1.6 s
    assert [e.seq for e in events] == [1, 2, 3, 4]
    assert [e.text for e in events] == [f"[es] Sentence {seq}." for seq in range(1, 5)]
    await fanout.stop()
