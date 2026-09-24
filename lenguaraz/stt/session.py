# SPDX-License-Identifier: Apache-2.0
"""ManagedSttSession: keeps one stage transcribing across session lifetimes and failures.

Responsibilities (spec 001 FR-001-03, FR-001-05, FR-001-06, FR-001-13):
- feed audio chunks from a queue into the engine session;
- turn engine events into ``Segment`` objects with a monotonically increasing ``seq``
  (all interims of an utterance share the ``seq`` of their final);
- compute ``t_audio_ms`` and ``latency_ms`` per segment;
- reopen the session on ``GoAway``, on the rotation timer and after transient errors,
  with exponential backoff + jitter; give up into ``STOPPED`` after too many failures;
- report every state change. Feature 003 upgrades the reopen into make-before-break.
"""

from __future__ import annotations

import asyncio
import contextlib
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from lenguaraz.config import StageConfig
from lenguaraz.models import StageState
from lenguaraz.stt.base import SttEngine, SttEvent, SttEventKind, SttSession

BYTES_PER_MS = 32

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
    last_detail: str | None = None
    states: list[StageState] = field(default_factory=list)


class ManagedSttSession:
    def __init__(
        self,
        stage: StageConfig,
        engine: SttEngine,
        *,
        emit: Callable[[Segment], None],
        on_state: StateCallback,
        rotate_seconds: float = 540.0,
        max_reconnects: int = 5,
        backoff_base: float = 0.5,
        backoff_cap: float = 10.0,
        drain_seconds: float = 3.0,
        sleep: SleepFn = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
        rng: Callable[[], float] = random.random,
    ) -> None:
        self._stage = stage
        self._engine = engine
        self._emit = emit
        self._on_state = on_state
        self._rotate_seconds = rotate_seconds
        self._max_reconnects = max_reconnects
        self._backoff_base = backoff_base
        self._backoff_cap = backoff_cap
        self._drain_seconds = drain_seconds
        self._sleep = sleep
        self._clock = clock
        self._rng = rng
        self.stats = SessionStats()
        self.state = StageState.IDLE
        self.session_id: str | None = None
        self._seq = 0
        self._start_wall: float | None = None

    # -- state -------------------------------------------------------------------------

    def _set_state(self, state: StageState, detail: str | None) -> None:
        self.state = state
        self.stats.last_detail = detail
        self.stats.states.append(state)
        self._on_state(state, detail)

    # -- timing ------------------------------------------------------------------------

    def t_audio_ms(self) -> int:
        return self.stats.bytes_sent // BYTES_PER_MS

    def latency_ms(self) -> int:
        if self._start_wall is None:
            return 0
        elapsed_ms = (self._clock() - self._start_wall) * 1000.0
        return max(0, round(elapsed_ms - self.t_audio_ms()))

    def _backoff(self, attempt: int) -> float:
        base = min(self._backoff_cap, self._backoff_base * (2 ** (attempt - 1)))
        return base * (0.5 + self._rng() / 2)

    # -- main loop ---------------------------------------------------------------------

    async def run(self, chunks: asyncio.Queue[bytes | None]) -> None:
        """Consume ``chunks`` (``None`` = source ended) until the source ends or we give up."""
        failures = 0
        self._set_state(StageState.STARTING, None)
        while True:
            try:
                session = await self._engine.open(self._stage)
            except Exception as exc:
                failures += 1
                self.stats.errors += 1
                if failures > self._max_reconnects:
                    self._set_state(
                        StageState.STOPPED, f"gave up after {failures - 1} reconnects: {exc}"
                    )
                    return
                delay = self._backoff(failures)
                self._set_state(
                    StageState.DEGRADED,
                    f"connect failed: {exc}; "
                    f"retry {failures}/{self._max_reconnects} in {delay:.1f}s",
                )
                await self._sleep(delay)
                continue

            self.stats.sessions_opened += 1
            self.session_id = getattr(session, "session_id", None)
            self._set_state(StageState.LIVE, None)
            outcome, detail = await self._run_session(session, chunks)

            if outcome == "done":
                self._set_state(StageState.STOPPED, "source ended")
                return
            if outcome == "rotate":
                failures = 0
                self.stats.rotations += 1
                self._set_state(StageState.ROTATING, detail)
                continue
            if outcome == "fatal":
                self.stats.errors += 1
                self._set_state(StageState.STOPPED, detail)
                return
            failures += 1
            self.stats.errors += 1
            if failures > self._max_reconnects:
                self._set_state(
                    StageState.STOPPED, f"gave up after {failures - 1} reconnects: {detail}"
                )
                return
            delay = self._backoff(failures)
            self._set_state(
                StageState.DEGRADED,
                f"{detail}; retry {failures}/{self._max_reconnects} in {delay:.1f}s",
            )
            await self._sleep(delay)

    async def _run_session(
        self, session: SttSession, chunks: asyncio.Queue[bytes | None]
    ) -> tuple[str, str | None]:
        """Run one session. Returns (outcome, detail); outcome ∈ done|rotate|error|fatal."""
        sender = asyncio.create_task(self._sender(session, chunks), name="stt-sender")
        receiver = asyncio.create_task(self._receiver(session), name="stt-receiver")
        timer = asyncio.create_task(self._rotation_timer(), name="stt-timer")
        try:
            done, _ = await asyncio.wait(
                {sender, receiver, timer}, return_when=asyncio.FIRST_COMPLETED
            )
            if sender in done:
                sender_error = sender.exception()
                if sender_error is not None:
                    return "error", f"send failed: {sender_error}"
                await self._safe(session.end_of_stream())
                with contextlib.suppress(asyncio.TimeoutError, Exception):
                    await asyncio.wait_for(asyncio.shield(receiver), self._drain_seconds)
                return "done", None
            if receiver in done:
                receiver_error = receiver.exception()
                if receiver_error is not None:
                    return "error", f"receive failed: {receiver_error}"
                return receiver.result()
            return "rotate", f"rotation timer ({self._rotate_seconds:.0f}s) elapsed"
        finally:
            for task in (sender, receiver, timer):
                if not task.done():
                    task.cancel()
            for task in (sender, receiver, timer):
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
            await self._safe(session.close())

    async def _rotation_timer(self) -> None:
        # Real clock on purpose: the injectable ``sleep`` is only for backoff.
        await asyncio.sleep(self._rotate_seconds)

    async def _sender(self, session: SttSession, chunks: asyncio.Queue[bytes | None]) -> None:
        while True:
            chunk = await chunks.get()
            if chunk is None:
                return
            if self._start_wall is None:
                self._start_wall = self._clock()
            await session.send(chunk)
            self.stats.bytes_sent += len(chunk)

    async def _receiver(self, session: SttSession) -> tuple[str, str | None]:
        async for event in session.events():
            kind = event.kind
            if kind is SttEventKind.INTERIM:
                if event.text.strip():
                    self.stats.interims += 1
                    self._emit(self._segment(event, is_final=False))
            elif kind is SttEventKind.FINAL:
                if event.text.strip():
                    self.stats.finals += 1
                    self._emit(self._segment(event, is_final=True))
                    self._seq += 1
            elif kind is SttEventKind.GO_AWAY:
                left = (
                    f"{event.time_left_s:.0f}s left" if event.time_left_s is not None else "GoAway"
                )
                return "rotate", f"server GoAway ({left})"
            elif kind is SttEventKind.USAGE:
                self.stats.prompt_tokens += event.prompt_tokens
                self.stats.response_tokens += event.response_tokens
                self.stats.total_tokens += event.total_tokens
            elif kind is SttEventKind.ERROR:
                if not event.retryable:
                    return "fatal", event.error
                return "error", event.error or "engine error"
        return "rotate", "session closed by server"

    def _segment(self, event: SttEvent, *, is_final: bool) -> Segment:
        return Segment(
            seq=self._seq,
            text=event.text.strip(),
            is_final=is_final,
            t_audio_ms=self.t_audio_ms(),
            latency_ms=self.latency_ms(),
            language=event.language_code,
        )

    @staticmethod
    async def _safe(awaitable: Awaitable[None]) -> None:
        with contextlib.suppress(Exception):
            await awaitable
