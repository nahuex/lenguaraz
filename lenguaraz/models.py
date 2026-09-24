# SPDX-License-Identifier: Apache-2.0
"""Public event models: the contract of ``WS /ws/{stage_id}?lang=`` (product.md §4)."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

__all__ = [
    "CaptionEvent",
    "Event",
    "MetricsEvent",
    "StageState",
    "StatusEvent",
    "WsCloseCode",
    "parse_event",
]


class StageState(StrEnum):
    """Every stage is always in exactly one of these (Constitution Art. VI.3)."""

    IDLE = "IDLE"
    STARTING = "STARTING"
    LIVE = "LIVE"
    ROTATING = "ROTATING"
    DEGRADED = "DEGRADED"
    STOPPED = "STOPPED"


class _Event(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    stage_id: str


class CaptionEvent(_Event):
    """One caption line. Interims share the ``seq`` of the final that replaces them."""

    type: Literal["caption"] = "caption"
    seq: int = Field(ge=0)
    lang: str
    source_lang: str
    is_final: bool
    text: str
    original: str | None = None
    t_audio_ms: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    degraded: bool = False


class StatusEvent(_Event):
    type: Literal["status"] = "status"
    state: StageState
    detail: str | None = None


class MetricsEvent(_Event):
    type: Literal["metrics"] = "metrics"
    p50_ms: int = Field(ge=0)
    p95_ms: int = Field(ge=0)
    rotations: int = Field(ge=0)
    errors: int = Field(ge=0)


Event = Annotated[CaptionEvent | StatusEvent | MetricsEvent, Field(discriminator="type")]

_event_adapter: TypeAdapter[CaptionEvent | StatusEvent | MetricsEvent] = TypeAdapter(Event)


def parse_event(data: bytes | str) -> CaptionEvent | StatusEvent | MetricsEvent:
    """Parse a JSON event (used by tests and tools that consume the WebSocket)."""
    return _event_adapter.validate_json(data)


class WsCloseCode:
    """Application close codes on the public WebSocket."""

    UNSUPPORTED_LANG = 4400
    UNKNOWN_STAGE = 4404
    RATE_LIMITED = 4429
    SLOW_CONSUMER = 4413
