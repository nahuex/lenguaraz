# SPDX-License-Identifier: Apache-2.0
"""Bus interface (Chasque). In-memory by default; a Redis implementation can plug in later."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from lenguaraz.models import CaptionEvent, MetricsEvent, StatusEvent

AnyEvent = CaptionEvent | StatusEvent | MetricsEvent


class Subscription(Protocol):
    """A bounded stream of events for one listener."""

    stage_id: str
    lang: str | None

    def __aiter__(self) -> AsyncIterator[AnyEvent]: ...

    async def get(self) -> AnyEvent: ...

    def close(self) -> None: ...

    @property
    def dropped(self) -> int: ...


class Bus(Protocol):
    def publish(self, stage_id: str, event: AnyEvent) -> None: ...

    def subscribe(
        self, stage_id: str, lang: str | None = None, *, internal: bool = False
    ) -> Subscription: ...

    def listeners(self, stage_id: str, lang: str | None = None) -> int: ...
