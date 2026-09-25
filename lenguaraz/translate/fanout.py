# SPDX-License-Identifier: Apache-2.0
"""Translation — translate every final caption into each active target language.

One ordered worker per (stage, language): finals are translated sequentially per language,
so captions never arrive out of order. Pass-through is inherent: a listener whose language
equals the caption's source language already receives the original from the bus. Errors
retry with backoff; a persistent failure leaves that sentence out of that language (counted) and the
original text, and reports a status detail, while STT captions keep flowing (FR-002-07).
Progressive translation (FR-002-06) translates a debounced partial hypothesis and publishes
it as an interim caption that the final later replaces (same ``seq``).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from lenguaraz.bus.base import Bus
from lenguaraz.config import Settings, StageConfig, short_code
from lenguaraz.models import CaptionEvent
from lenguaraz.translate.base import (
    TranslationEngine,
    TranslationError,
    TranslationOutcome,
    TranslationRequest,
    TranslationUsage,
)
from lenguaraz.translate.demand import LanguageDemand

log = logging.getLogger("lenguaraz.translate")

QUEUE_SIZE = 100
BACKOFF_SECONDS = (0.5, 1.0, 2.0)
# 429: pause the language for the server's retry hint instead of hammering (spec 002 FR-002-14)
COOLDOWN_DEFAULT_SECONDS = 30.0
COOLDOWN_MIN_SECONDS = 5.0
COOLDOWN_MAX_SECONDS = 120.0
RETRY_HINT = re.compile(r"retry in ([0-9.]+)s", re.IGNORECASE)
StatusCallback = Callable[[str], None]
SleepFn = Callable[[float], Awaitable[None]]


@dataclass(slots=True)
class _Progressive:
    last_text: str = ""
    last_time: float = -1e9
    task: asyncio.Task[None] | None = None


@dataclass(slots=True)
class _Language:
    queue: asyncio.Queue[CaptionEvent]
    worker: asyncio.Task[None] | None = None
    inflight: set[asyncio.Task[None]] = field(default_factory=set)
    turn: asyncio.Future[None] | None = None
    context: deque[tuple[str, str]] = field(default_factory=lambda: deque(maxlen=3))
    usage: TranslationUsage = field(default_factory=TranslationUsage)
    progressive: _Progressive = field(default_factory=_Progressive)
    dropped: int = 0
    cooldown_until: float = 0.0
    rate_limited: int = 0
    untranslated: int = 0
    hedged: int = 0
    last_final_seq: int = -1


class TranslationFanout:
    def __init__(
        self,
        stage: StageConfig,
        engine: TranslationEngine,
        bus: Bus,
        settings: Settings,
        *,
        on_status: StatusCallback | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: SleepFn = asyncio.sleep,
    ) -> None:
        self._stage = stage
        self._engine = engine
        self._bus = bus
        self._settings = settings
        self._on_status = on_status
        self._clock = clock
        self._sleep = sleep
        self._languages: dict[str, _Language] = {}
        self.demand = LanguageDemand(
            [code for code in settings.always_on() if code in stage.targets],
            settings.lang_grace_seconds,
            clock=clock,
        )
        self._log = logging.LoggerAdapter(log, {"stage_id": stage.id, "component": "translation"})

    # -- language demand ---------------------------------------------------------------

    def active_languages(self) -> list[str]:
        listening = getattr(self._bus, "languages_with_listeners", None)
        if listening is not None:
            self.demand.observe(listening(self._stage.id))
        return self.demand.active(candidates=self._stage.targets)

    def usage(self) -> dict[str, dict[str, int]]:
        return {code: lang.usage.as_dict() for code, lang in self._languages.items()}

    def hedged(self) -> int:
        """Extra (hedged) translation requests sent because the first one was slow."""
        return sum(lang.hedged for lang in self._languages.values())

    def untranslated(self) -> int:
        """Finals that were left out of a language because translation failed or was paused."""
        return sum(lang.untranslated for lang in self._languages.values())

    def rate_limited(self) -> int:
        """How many times a 429 paused a language (all languages)."""
        return sum(lang.rate_limited for lang in self._languages.values())

    # -- entry point -----------------------------------------------------------------------

    def on_caption(self, event: CaptionEvent) -> None:
        """Called after the original caption was published on the bus."""
        source = short_code(event.lang)
        targets = [code for code in self.active_languages() if code != source]
        if not targets:
            return
        if event.is_final:
            for code in targets:
                self._enqueue(code, event)
        elif self._settings.progressive_translation:
            for code in targets:
                self._maybe_progressive(code, event)

    async def stop(self) -> None:
        tasks: list[asyncio.Task[None]] = []
        for lang in self._languages.values():
            if lang.worker is not None:
                tasks.append(lang.worker)
            if lang.progressive.task is not None:
                tasks.append(lang.progressive.task)
            tasks.extend(lang.inflight)
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._languages.clear()

    # -- finals: ordered worker per language -------------------------------------------------

    def _language(self, code: str) -> _Language:
        lang = self._languages.get(code)
        if lang is None:
            lang = _Language(queue=asyncio.Queue(maxsize=QUEUE_SIZE))
            lang.context = deque(maxlen=max(0, self._settings.translate_context_segments))
            self._languages[code] = lang
        if lang.worker is None or lang.worker.done():
            lang.worker = asyncio.create_task(self._worker(code, lang), name=f"translate-{code}")
        return lang

    def _enqueue(self, code: str, event: CaptionEvent) -> None:
        lang = self._language(code)
        if lang.queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                lang.queue.get_nowait()  # keep the newest finals when hopelessly behind
                lang.dropped += 1
        lang.queue.put_nowait(event)

    async def _worker(self, code: str, lang: _Language) -> None:
        """Translate up to ``translate_concurrency`` finals at once, publish them in order."""
        limit = max(1, self._settings.translate_concurrency)
        gate = asyncio.Semaphore(limit)
        while True:
            event = await lang.queue.get()
            await gate.acquire()
            previous = lang.turn
            mine: asyncio.Future[None] = asyncio.get_running_loop().create_future()
            lang.turn = mine
            task = asyncio.create_task(
                self._translate_in_turn(code, lang, event, previous, mine, gate),
                name=f"translate-{code}-{event.seq}",
            )
            lang.inflight.add(task)
            task.add_done_callback(lang.inflight.discard)

    async def _translate_in_turn(
        self,
        code: str,
        lang: _Language,
        event: CaptionEvent,
        previous: asyncio.Future[None] | None,
        mine: asyncio.Future[None],
        gate: asyncio.Semaphore,
    ) -> None:
        try:
            started = self._clock()
            text = await self._translate(code, lang, event, is_final=True)
            if previous is not None:
                # keep publication order, but never let one slow sentence freeze the view
                wait = self._settings.translate_order_wait_ms / 1000.0
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(asyncio.shield(previous), wait)
            if text is not None:
                if event.seq < lang.last_final_seq:
                    # a later sentence is already on screen: showing this one now would
                    # break the order, so it is left out of this language
                    self._skip(code, lang, True, "arrived after a later sentence")
                else:
                    lang.last_final_seq = event.seq
                    self._publish(code, event, text, is_final=True, started=started)
        finally:
            if not mine.done():
                mine.set_result(None)
            gate.release()

    # -- progressive translation of partials --------------------------------------------------

    def _maybe_progressive(self, code: str, event: CaptionEvent) -> None:
        lang = self._language(code)
        state = lang.progressive
        if self._clock() < lang.cooldown_until:
            return  # rate limited: partials are not worth a request
        if len(event.text.split()) < self._settings.progressive_min_words:
            return
        if event.text == state.last_text:
            return
        now = self._clock()
        if now - state.last_time < self._settings.progressive_debounce_ms / 1000.0:
            return
        if state.task is not None and not state.task.done():
            return
        state.last_text = event.text
        state.last_time = now
        state.task = asyncio.create_task(
            self._translate_and_publish(code, lang, event, is_final=False),
            name=f"translate-progressive-{code}",
        )

    # -- one translation ---------------------------------------------------------------------

    async def _translate_and_publish(
        self, code: str, lang: _Language, event: CaptionEvent, *, is_final: bool
    ) -> None:
        started = self._clock()
        text = await self._translate(code, lang, event, is_final=is_final)
        if text is not None:
            self._publish(code, event, text, is_final=is_final, started=started)

    async def _translate(
        self, code: str, lang: _Language, event: CaptionEvent, *, is_final: bool
    ) -> str | None:
        """Translate one caption; ``None`` means the sentence is skipped in this language."""
        request = TranslationRequest(
            text=event.text,
            source_lang=event.lang,
            target_lang=code,
            glossary=tuple(self._stage.glossary),
            context=tuple(lang.context),
            talk_title=self._stage.talk.title,
            talk_abstract=self._stage.talk.abstract,
        )
        started = self._clock()
        if started < lang.cooldown_until:
            self._skip(code, lang, is_final, "rate limited")
            return None
        last_error: Exception | None = None
        for attempt, delay in enumerate((*BACKOFF_SECONDS, None), start=1):
            try:
                outcome = await self._hedged_translate(request, lang)
            except TranslationError as exc:
                if exc.code == 429:
                    self._rate_limited(code, lang, exc)
                    self._skip(code, lang, is_final, "rate limited")
                    return None
                last_error = exc
                if not exc.retryable or delay is None:
                    break
                self._log.warning("translation to %s failed (attempt %d): %s", code, attempt, exc)
                await self._sleep(delay)
                continue
            except asyncio.CancelledError:
                raise
            except TimeoutError:
                last_error = TranslationError(
                    f"timed out after {self._settings.translate_timeout_seconds:.0f}s"
                )
                break  # a slow model must not hold the whole language queue: degrade now
            except Exception as exc:
                last_error = exc
                self._log.exception("translation engine crashed")
                break
            lang.usage.add(outcome.usage)
            if is_final:
                lang.context.append((event.text, outcome.text))
            return outcome.text
        detail = f"translation to {code} failed: {last_error}"
        self._log.error(detail)
        if self._on_status is not None:
            self._on_status(detail)
        self._skip(code, lang, is_final, str(last_error))
        return None

    async def _hedged_translate(
        self, request: TranslationRequest, lang: _Language
    ) -> TranslationOutcome:
        """Hedged requests (tail-latency best practice): if the first call has not answered after
        ``translate_hedge_after_ms``, send an identical one; the first success wins and the rest
        are cancelled. Measured 2026-09-25: parallel calls to the same model returned in 38.3 s,
        1.6 s and 1.7 s, so slowness is per request and hedging removes most of the tail."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._settings.translate_timeout_seconds
        hedge_after = self._settings.translate_hedge_after_ms / 1000.0
        max_attempts = 1 + (self._settings.translate_hedges if hedge_after > 0 else 0)
        pending: set[asyncio.Task[TranslationOutcome]] = set()
        last_error: BaseException | None = None
        attempts = 0

        def launch() -> None:
            nonlocal attempts
            attempts += 1
            pending.add(asyncio.create_task(self._engine.translate(request)))

        launch()
        try:
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise TimeoutError
                can_hedge = attempts < max_attempts
                wait = min(remaining, hedge_after) if can_hedge else remaining
                done: set[asyncio.Task[TranslationOutcome]] = set()
                if pending:
                    done, _ = await asyncio.wait(
                        pending, timeout=wait, return_when=asyncio.FIRST_COMPLETED
                    )
                for task in done:
                    pending.discard(task)
                    error = task.exception()
                    if error is None:
                        return task.result()
                    last_error = error
                    if isinstance(error, TranslationError) and error.code == 429:
                        raise error  # rate limited: more copies would make it worse
                if not pending:
                    # every copy failed: let the caller's retry-with-backoff handle the error
                    raise last_error if last_error is not None else TimeoutError()
                if can_hedge and not done:
                    # hedge only on slowness, never on errors
                    launch()
                    lang.hedged += 1
        finally:
            for task in pending:
                task.cancel()

    def _skip(self, code: str, lang: _Language, is_final: bool, reason: str) -> None:
        """Each language view shows only its own language (owner decision, 2026-09-25): a
        sentence whose translation fails is left out of that language and counted; the original
        stays available in its own view. Nothing is published for it."""
        if is_final:
            lang.untranslated += 1
        self._log.info("translation to %s skipped (%s)", code, reason)

    def _rate_limited(self, code: str, lang: _Language, exc: TranslationError) -> None:
        match = RETRY_HINT.search(str(exc))
        seconds = float(match.group(1)) if match else COOLDOWN_DEFAULT_SECONDS
        seconds = min(max(seconds, COOLDOWN_MIN_SECONDS), COOLDOWN_MAX_SECONDS)
        lang.cooldown_until = self._clock() + seconds
        lang.rate_limited += 1
        detail = (
            f"rate limited (429): translation to {code} paused for {seconds:.0f}s; "
            "sentences are skipped in that language meanwhile"
        )
        self._log.warning(detail)
        if self._on_status is not None:
            self._on_status(detail)

    def _publish(
        self,
        code: str,
        event: CaptionEvent,
        text: str,
        *,
        is_final: bool,
        started: float,
        degraded: bool = False,
    ) -> None:
        self._bus.publish(
            self._stage.id,
            CaptionEvent(
                stage_id=self._stage.id,
                seq=event.seq,
                lang=code,
                source_lang=short_code(event.lang),
                is_final=is_final,
                text=text,
                original=event.text,
                t_audio_ms=event.t_audio_ms,
                latency_ms=max(0, round((self._clock() - started) * 1000)),
                degraded=degraded,
            ),
        )
