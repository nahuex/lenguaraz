# SPDX-License-Identifier: Apache-2.0
"""In-memory bus with bounded per-subscriber queues and backpressure.

Eviction policy (Constitution Art. VII.2, prior art PA-1 L4): when a subscriber's
queue is full, drop its oldest *interim* caption first. Finals and status events are
never dropped: if there is nothing droppable left, the subscriber is too slow and is
closed (the WebSocket layer reports ``SLOW_CONSUMER`` and the client reconnects).
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator

from lenguaraz.bus.base import AnyEvent
from lenguaraz.models import CaptionEvent

DEFAULT_QUEUE_SIZE = 200


class SlowConsumerError(Exception):
    """The subscriber could not keep up and a final/status would have been dropped."""


class MemorySubscription:
    def __init__(self, bus: MemoryBus, stage_id: str, lang: str | None, maxsize: int) -> None:
        self._bus = bus
        self.stage_id = stage_id
        self.lang = lang
        self._maxsize = maxsize
        self._queue: deque[AnyEvent] = deque()
        self._ready = asyncio.Event()
        self._dropped = 0
        self._closed = False
        self._overflowed = False

    @property
    def dropped(self) -> int:
        return self._dropped

    @property
    def closed(self) -> bool:
        return self._closed

    def _offer(self, event: AnyEvent) -> None:
        if self._closed:
            return
        if isinstance(event, CaptionEvent) and self.lang is not None and event.lang != self.lang:
            return
        if len(self._queue) >= self._maxsize:
            for index, queued in enumerate(self._queue):
                if isinstance(queued, CaptionEvent) and not queued.is_final:
                    del self._queue[index]
                    self._dropped += 1
                    break
            else:
                if isinstance(event, CaptionEvent) and not event.is_final:
                    self._dropped += 1  # drop the incoming interim, keep what is queued
                    return
                self._overflowed = True  # a final/status would be lost: fail loudly
                self._ready.set()
                self._bus._remove(self)
                self._closed = True
                return
        self._queue.append(event)
        self._ready.set()

    async def get(self) -> AnyEvent:
        while not self._queue:
            if self._overflowed:
                raise SlowConsumerError(self.stage_id)
            if self._closed:
                raise StopAsyncIteration
            self._ready.clear()
            await self._ready.wait()
        return self._queue.popleft()

    def __aiter__(self) -> AsyncIterator[AnyEvent]:
        return self

    async def __anext__(self) -> AnyEvent:
        return await self.get()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._bus._remove(self)
            self._ready.set()


class MemoryBus:
    def __init__(self, queue_size: int = DEFAULT_QUEUE_SIZE) -> None:
        self._queue_size = queue_size
        self._subs: dict[str, set[MemorySubscription]] = {}

    def publish(self, stage_id: str, event: AnyEvent) -> None:
        for sub in tuple(self._subs.get(stage_id, ())):
            sub._offer(event)

    def subscribe(self, stage_id: str, lang: str | None = None) -> MemorySubscription:
        sub = MemorySubscription(self, stage_id, lang, self._queue_size)
        self._subs.setdefault(stage_id, set()).add(sub)
        return sub

    def listeners(self, stage_id: str, lang: str | None = None) -> int:
        subs = self._subs.get(stage_id, ())
        if lang is None:
            return len(subs)
        return sum(1 for sub in subs if sub.lang == lang)

    def languages_with_listeners(self, stage_id: str) -> set[str]:
        return {sub.lang for sub in self._subs.get(stage_id, ()) if sub.lang is not None}

    def _remove(self, sub: MemorySubscription) -> None:
        subs = self._subs.get(sub.stage_id)
        if subs is not None:
            subs.discard(sub)
            if not subs:
                del self._subs[sub.stage_id]
