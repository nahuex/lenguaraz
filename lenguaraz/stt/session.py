# SPDX-License-Identifier: Apache-2.0
"""ManagedSttSession: keeps one stage transcribing across session lifetimes and failures.

Responsibilities (spec 001 FR-001-03/05/06/13, spec 003 FR-003-01/02/03/06/07):
- feed audio chunks from a queue into the *active* engine session (one writer);
- in hybrid VAD mode, send ``audio_stream_end`` after speech + silence (fast finalization);
- turn engine events into ``Segment`` objects with a monotonically increasing ``seq`` that
  continues across sessions (all interims of an utterance share the ``seq`` of their final);
- **Posta, make-before-break rotation:** on the rotation timer or the server's ``GoAway``,
  open the next session while the current one keeps listening, switch the audio feed only
  when it is connected, then let the old session drain its last finals before closing it;
- drop late duplicates (same normalized text within a short window) and measure the caption
  gap of every rotation on the audio timeline;
- reconnect with exponential backoff + jitter after errors; give up into ``STOPPED`` after
  too many consecutive failures; report every state change.
"""

from __future__ import annotations

import asyncio
import contextlib
import math
import random
import re
import time
from array import array
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from lenguaraz.config import StageConfig
from lenguaraz.models import StageState
from lenguaraz.stt.base import SttEngine, SttEvent, SttEventKind, SttSession

BYTES_PER_MS = 32
DEDUPE_MEMORY = 20

StateCallback = Callable[[StageState, str | None], None]
SleepFn = Callable[[float], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class Segment:
    seq: int
    text: str
    is_final: bool
    t_audio_ms: int
    latency_ms: int
    language: str | None = None


@dataclass(slots=True)
class SessionStats:
    sessions_opened: int = 0
    rotations: int = 0
    errors: int = 0
    bytes_sent: int = 0
    finals: int = 0
    interims: int = 0
    prompt_tokens: int = 0
    response_tokens: int = 0
    total_tokens: int = 0
    vad_signals: int = 0
    duplicates_dropped: int = 0
    stalls: int = 0
    last_rotation_gap_ms: int | None = None
    last_detail: str | None = None
    states: list[StageState] = field(default_factory=list)


def normalize_text(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def chunk_rms(chunk: bytes) -> float:
    """Root mean square of a s16le chunk (0 for empty)."""
    samples = array("h")
    samples.frombytes(chunk[: len(chunk) - len(chunk) % 2])
    if not samples:
        return 0.0
    return math.sqrt(sum(v * v for v in samples) / len(samples))


class ManagedSttSession:
    def __init__(
        self,
        stage: StageConfig,
        engine: SttEngine,
        *,
        emit: Callable[[Segment], None],
        on_state: StateCallback,
        rotate_seconds: float = 540.0,
        vad_silence_ms: int | None = None,
        vad_threshold: int = 300,
        max_reconnects: int = 5,
        backoff_base: float = 0.5,
        backoff_cap: float = 10.0,
        drain_seconds: float = 3.0,
        dedupe_window: float = 5.0,
        swap_max_wait: float = 8.0,
        stall_seconds: float = 20.0,
        sleep: SleepFn = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
        rng: Callable[[], float] = random.random,
    ) -> None:
        self._stage = stage
        self._engine = engine
        self._emit = emit
        self._on_state = on_state
        self._rotate_seconds = rotate_seconds
        self._vad_silence_ms = vad_silence_ms
        self._vad_threshold = vad_threshold
        self._max_reconnects = max_reconnects
        self._backoff_base = backoff_base
        self._backoff_cap = backoff_cap
        self._drain_seconds = drain_seconds
        self._dedupe_window = dedupe_window
        self._swap_max_wait = swap_max_wait
        self._stall_seconds = stall_seconds
        self._last_speech_wall: float | None = None
        self._last_caption_wall: float | None = None
        self._pending: SttSession | None = None
        self._watchdog_task: asyncio.Task[None] | None = None
        self._sleep = sleep
        self._clock = clock
        self._rng = rng
        self.stats = SessionStats()
        self.state = StageState.IDLE
        self.session_id: str | None = None
        self._seq = 0
        self._start_wall: float | None = None
        self._last_interim_wall: float | None = None
        self._failures = 0
        self._last_open_error: str | None = None
        self._active: SttSession | None = None
        self._active_ready = asyncio.Event()
        self._receiver_task: asyncio.Task[tuple[str, str | None]] | None = None
        self._timer_task: asyncio.Task[None] | None = None
        self._draining: set[asyncio.Task[None]] = set()
        self._rotate_requested = asyncio.Event()
        self._rotate_reason: str | None = None
        self._recent_finals: deque[tuple[str, float]] = deque(maxlen=DEDUPE_MEMORY)
        self._last_final_audio_ms = 0
        self._gap_pending = False
        self._audio_before_swap = 0

    # -- state -------------------------------------------------------------------------

    def _set_state(self, state: StageState, detail: str | None) -> None:
        self.state = state
        self.stats.last_detail = detail
        self.stats.states.append(state)
        self._on_state(state, detail)

    # -- timing ------------------------------------------------------------------------

    @property
    def stream_start(self) -> float | None:
        """Monotonic wall time at which the first audio chunk was sent."""
        return self._start_wall

    def t_audio_ms(self) -> int:
        return self.stats.bytes_sent // BYTES_PER_MS

    def latency_ms(self) -> int:
        """Milliseconds since the previous partial update of the current utterance.

        For an interim this is the update gap; for a final it is the commit delay (last
        partial update → committed line). 0 when there is no previous partial. True
        speech-to-caption latency is measured by ``make smoke-stt`` with known sentence
        boundaries (spec 001 FR-001-13, amended 2026-09-24).
        """
        if self._last_interim_wall is None:
            return 0
        return max(0, round((self._clock() - self._last_interim_wall) * 1000.0))

    def _backoff(self, attempt: int) -> float:
        base = min(self._backoff_cap, self._backoff_base * (2 ** (attempt - 1)))
        return base * (0.5 + self._rng() / 2)

    # -- main loop ---------------------------------------------------------------------

    async def run(self, chunks: asyncio.Queue[bytes | None]) -> None:
        """Consume ``chunks`` (``None`` = source ended) until the source ends or we give up."""
        self._set_state(StageState.STARTING, None)
        session = await self._open_with_retries(rotating=False)
        if session is None:
            return
        self._activate(session)
        sender = asyncio.create_task(self._sender(chunks), name="stt-sender")
        try:
            while True:
                receiver = self._receiver_task
                assert receiver is not None
                waiter = asyncio.create_task(self._rotate_requested.wait(), name="stt-rotate")
                done, _ = await asyncio.wait(
                    {sender, receiver, waiter},
                    timeout=self._stall_seconds / 4 if self._stall_seconds > 0 else None,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if not waiter.done():
                    waiter.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await waiter

                if not done:
                    # periodic check: speech keeps flowing but the server sends nothing (spec 007)
                    if self._stalled() and not await self._handle_stall():
                        return
                    continue

                if sender in done:
                    error = sender.exception()
                    if error is None:
                        await self._finish_source()
                        return
                    if not await self._recover(f"send failed: {error}"):
                        return
                    sender = asyncio.create_task(self._sender(chunks), name="stt-sender")
                    continue

                if receiver is not self._receiver_task:
                    continue  # the sender swapped sessions at a pause; that receiver is the old one

                if waiter in done:
                    await self._rotate()
                    continue  # a result from the previous receiver belongs to the old session

                if receiver in done:
                    detail: str | None
                    if receiver.exception() is not None:
                        kind, detail = "error", f"receive failed: {receiver.exception()}"
                    else:
                        kind, detail = receiver.result()
                    if kind == "fatal":
                        self.stats.errors += 1
                        self._set_state(StageState.STOPPED, detail)
                        return
                    if kind == "error":
                        if not await self._recover(detail or "engine error"):
                            return
                        continue
                    # the server closed the active session without a GoAway we could act on
                    if not await self._replace_dead_session(detail):
                        return
        finally:
            await self._cleanup(sender)

    # -- sessions ----------------------------------------------------------------------

    async def _open_with_retries(self, *, rotating: bool) -> SttSession | None:
        """Open a session with backoff. When ``rotating`` the current session keeps running."""
        while True:
            try:
                session = await self._engine.open(self._stage)
            except Exception as exc:
                self._failures += 1
                self.stats.errors += 1
                self._last_open_error = str(exc)
                if self._failures > self._max_reconnects:
                    if not rotating:
                        self._set_state(
                            StageState.STOPPED,
                            f"gave up after {self._failures - 1} reconnects: {exc}",
                        )
                    return None
                delay = self._backoff(self._failures)
                retry = f"retry {self._failures}/{self._max_reconnects} in {delay:.1f}s"
                if rotating:
                    self._set_state(StageState.ROTATING, f"next session failed: {exc}; {retry}")
                else:
                    self._set_state(StageState.DEGRADED, f"connect failed: {exc}; {retry}")
                await self._sleep(delay)
                continue
            self.stats.sessions_opened += 1
            return session

    def _activate(self, session: SttSession) -> None:
        self._active = session
        self.session_id = getattr(session, "session_id", None)
        self._receiver_task = asyncio.create_task(self._receiver(session), name="stt-receiver")
        self._last_caption_wall = self._clock()
        self._active_ready.set()
        self._failures = 0
        self._set_state(StageState.LIVE, None)
        self._arm_timer()

    async def _rotate(self) -> None:
        reason = self._rotate_reason or "rotation"
        self._rotate_requested.clear()
        self._rotate_reason = None
        self._set_state(StageState.ROTATING, reason)
        new = await self._open_with_retries(rotating=True)
        if new is None:
            self._failures = 0
            self._set_state(StageState.LIVE, f"rotation postponed: {self._last_open_error}")
            self._arm_timer()
            return
        if self._vad_silence_ms is None:
            self._swap(new)
            return
        # Hybrid VAD: switch the feed at the next pause so no utterance is split (spec 003).
        self._pending = new
        self._set_state(StageState.ROTATING, "next session ready; switching at the next pause")
        self._watchdog_task = asyncio.create_task(self._swap_watchdog(), name="stt-swap-wait")

    def _swap(self, new: SttSession) -> None:
        old, old_receiver = self._active, self._receiver_task
        self._pending = None
        if self._watchdog_task is not None and not self._watchdog_task.done():
            self._watchdog_task.cancel()
        self._audio_before_swap = self._last_final_audio_ms
        self._gap_pending = True
        self._activate(new)
        self.stats.rotations += 1
        if old is not None:
            task = asyncio.create_task(self._drain_and_close(old, old_receiver), name="stt-drain")
            self._draining.add(task)
            task.add_done_callback(self._draining.discard)

    async def _swap_watchdog(self) -> None:
        await asyncio.sleep(self._swap_max_wait)
        if self._pending is not None:
            self._swap(self._pending)

    def _stalled(self) -> bool:
        """True when speech was heard after the last caption and the window has expired."""
        if self._stall_seconds <= 0 or self._active is None or self._pending is not None:
            return False
        speech, caption = self._last_speech_wall, self._last_caption_wall
        if speech is None or caption is None or speech <= caption:
            return False
        now = self._clock()
        return now - caption > self._stall_seconds and now - speech <= self._stall_seconds

    async def _handle_stall(self) -> bool:
        """Close the silent session and open a new one; counted separately from errors."""
        self.stats.stalls += 1
        old, receiver = self._active, self._receiver_task
        self._active = None
        self._active_ready.clear()
        if receiver is not None and not receiver.done():
            receiver.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await receiver
        if old is not None:
            await self._safe(old.close())
        detail = f"no transcription for {self._stall_seconds:.0f}s while speech is flowing (stall)"
        return await self._replace_dead_session(detail)

    async def _replace_dead_session(self, detail: str | None) -> bool:
        self._rotate_requested.clear()
        self._rotate_reason = None
        self._active = None
        self._active_ready.clear()
        self.stats.rotations += 1
        self._set_state(StageState.ROTATING, detail or "session closed by server")
        new = self._take_pending() or await self._open_with_retries(rotating=False)
        if new is None:
            return False
        self._audio_before_swap = self._last_final_audio_ms
        self._gap_pending = True
        self._activate(new)
        return True

    def _take_pending(self) -> SttSession | None:
        pending, self._pending = self._pending, None
        if self._watchdog_task is not None and not self._watchdog_task.done():
            self._watchdog_task.cancel()
        return pending

    async def _recover(self, detail: str) -> bool:
        """Close the active session after an error and reopen with backoff."""
        old = self._active
        self._active = None
        self._active_ready.clear()
        if old is not None:
            await self._safe(old.close())
        self._failures += 1
        self.stats.errors += 1
        if self._failures > self._max_reconnects:
            self._set_state(
                StageState.STOPPED, f"gave up after {self._failures - 1} reconnects: {detail}"
            )
            return False
        delay = self._backoff(self._failures)
        self._set_state(
            StageState.DEGRADED,
            f"{detail}; retry {self._failures}/{self._max_reconnects} in {delay:.1f}s",
        )
        await self._sleep(delay)
        new = self._take_pending() or await self._open_with_retries(rotating=False)
        if new is None:
            return False
        self._activate(new)
        return True

    async def _drain_and_close(
        self, old: SttSession, old_receiver: asyncio.Task[tuple[str, str | None]] | None
    ) -> None:
        try:
            await self._safe(old.end_of_stream())
            if old_receiver is not None and not old_receiver.done():
                with contextlib.suppress(TimeoutError, asyncio.TimeoutError, Exception):
                    await asyncio.wait_for(asyncio.shield(old_receiver), self._drain_seconds)
        finally:
            await self._safe(old.close())
            if old_receiver is not None and not old_receiver.done():
                old_receiver.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await old_receiver

    async def _finish_source(self) -> None:
        active, receiver = self._active, self._receiver_task
        if active is not None and self.stats.bytes_sent:
            await self._safe(active.end_of_stream())
            if receiver is not None and not receiver.done():
                with contextlib.suppress(TimeoutError, asyncio.TimeoutError, Exception):
                    await asyncio.wait_for(asyncio.shield(receiver), self._drain_seconds)
        self._set_state(StageState.STOPPED, "source ended")

    async def _cleanup(self, sender: asyncio.Task[None]) -> None:
        tasks: list[asyncio.Task[object]] = [sender]
        if self._timer_task is not None:
            tasks.append(self._timer_task)
        if self._receiver_task is not None:
            tasks.append(self._receiver_task)
        tasks.extend(self._draining)
        for task in tasks:
            if not task.done():
                task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if self._watchdog_task is not None and not self._watchdog_task.done():
            self._watchdog_task.cancel()
        if self._pending is not None:
            await self._safe(self._pending.close())
            self._pending = None
        if self._active is not None:
            await self._safe(self._active.close())
            self._active = None

    # -- rotation trigger ----------------------------------------------------------------

    def _request_rotate(self, reason: str) -> None:
        if not self._rotate_requested.is_set():
            self._rotate_reason = reason
            self._rotate_requested.set()

    def _arm_timer(self) -> None:
        if self._timer_task is not None and not self._timer_task.done():
            self._timer_task.cancel()
        self._timer_task = asyncio.create_task(self._rotation_timer(), name="stt-timer")

    async def _rotation_timer(self) -> None:
        # Real clock on purpose: the injectable ``sleep`` is only for backoff.
        await asyncio.sleep(self._rotate_seconds)
        self._request_rotate(f"rotation timer ({self._rotate_seconds:.0f}s) elapsed")

    # -- audio in ------------------------------------------------------------------------

    async def _sender(self, chunks: asyncio.Queue[bytes | None]) -> None:
        """Forward audio to the active session; hybrid VAD signals ``audio_stream_end``."""
        speech_seen = False
        silence_ms = 0
        while True:
            chunk = await chunks.get()
            if chunk is None:
                return
            await self._active_ready.wait()
            session = self._active
            if session is None:
                continue
            if self._start_wall is None:
                self._start_wall = self._clock()
            await session.send(chunk)
            self.stats.bytes_sent += len(chunk)
            loud = chunk_rms(chunk) >= self._vad_threshold
            if loud:
                self._last_speech_wall = self._clock()
            if self._vad_silence_ms is None:
                continue
            if loud:
                speech_seen = True
                silence_ms = 0
            elif speech_seen:
                silence_ms += len(chunk) // BYTES_PER_MS
                if silence_ms >= self._vad_silence_ms:
                    await session.end_of_stream()
                    self.stats.vad_signals += 1
                    speech_seen = False
                    silence_ms = 0
                    if self._pending is not None:
                        self._swap(self._pending)

    # -- events out ----------------------------------------------------------------------

    async def _receiver(self, session: SttSession) -> tuple[str, str | None]:
        async for event in session.events():
            kind = event.kind
            if kind is SttEventKind.INTERIM:
                if event.text.strip():
                    segment = self._segment(event, session, is_final=False)
                    if segment is not None:
                        self.stats.interims += 1
                        self._emit(segment)
            elif kind is SttEventKind.FINAL:
                if event.text.strip():
                    segment = self._segment(event, session, is_final=True)
                    if segment is not None:
                        self.stats.finals += 1
                        self._emit(segment)
                        self._seq += 1
            elif kind is SttEventKind.GO_AWAY:
                if session is self._active:
                    left = (
                        f"{event.time_left_s:.0f}s left"
                        if event.time_left_s is not None
                        else "GoAway"
                    )
                    self._request_rotate(f"server GoAway ({left})")
            elif kind is SttEventKind.USAGE:
                self.stats.prompt_tokens += event.prompt_tokens
                self.stats.response_tokens += event.response_tokens
                self.stats.total_tokens += event.total_tokens
            elif kind is SttEventKind.ERROR:
                if session is not self._active:
                    return "closed", event.error
                if not event.retryable:
                    return "fatal", event.error
                return "error", event.error or "engine error"
        return "closed", "session closed by server"

    def _segment(self, event: SttEvent, session: SttSession, *, is_final: bool) -> Segment | None:
        text = event.text.strip()
        now = self._clock()
        if is_final:
            key = normalize_text(text)
            for seen, stamp in self._recent_finals:
                if seen == key and now - stamp <= self._dedupe_window:
                    self.stats.duplicates_dropped += 1
                    return None
            self._recent_finals.append((key, now))
        t_audio = self.t_audio_ms()
        if self._gap_pending and session is self._active:
            # audio-timeline distance from the last committed final to the first caption of
            # the new session (includes the natural pause between sentences)
            self.stats.last_rotation_gap_ms = max(0, t_audio - self._last_final_audio_ms)
            self._gap_pending = False
        segment = Segment(
            seq=self._seq,
            text=text,
            is_final=is_final,
            t_audio_ms=t_audio,
            latency_ms=self.latency_ms(),
            language=event.language_code,
        )
        self._last_caption_wall = now
        if is_final:
            self._last_final_audio_ms = t_audio
            self._last_interim_wall = None
        else:
            self._last_interim_wall = now
        return segment

    @staticmethod
    async def _safe(awaitable: Awaitable[None]) -> None:
        with contextlib.suppress(Exception):
            await awaitable
