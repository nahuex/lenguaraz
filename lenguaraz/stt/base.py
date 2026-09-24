# SPDX-License-Identifier: Apache-2.0
"""STT engine interface (Constitution Art. XIII.1: one of the two explicit interfaces)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from lenguaraz.config import StageConfig


class SttEventKind(StrEnum):
    INTERIM = "interim"
    FINAL = "final"
    GO_AWAY = "go_away"
    USAGE = "usage"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class SttEvent:
    """One event from a live transcription session."""

    kind: SttEventKind
    text: str = ""
    language_code: str | None = None
    time_left_s: float | None = None
    prompt_tokens: int = 0
    response_tokens: int = 0
    total_tokens: int = 0
    error: str | None = None
    code: int | None = None
    retryable: bool = True

    @classmethod
    def interim(cls, text: str, language_code: str | None = None) -> SttEvent:
        return cls(SttEventKind.INTERIM, text=text, language_code=language_code)

    @classmethod
    def final(cls, text: str, language_code: str | None = None) -> SttEvent:
        return cls(SttEventKind.FINAL, text=text, language_code=language_code)

    @classmethod
    def go_away(cls, time_left_s: float | None) -> SttEvent:
        return cls(SttEventKind.GO_AWAY, time_left_s=time_left_s)

    @classmethod
    def usage(cls, prompt_tokens: int, response_tokens: int, total_tokens: int) -> SttEvent:
        return cls(
            SttEventKind.USAGE,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            total_tokens=total_tokens,
        )

    @classmethod
    def failure(cls, error: str, code: int | None = None, retryable: bool = True) -> SttEvent:
        return cls(SttEventKind.ERROR, error=error, code=code, retryable=retryable)


class SttSession(Protocol):
    """One live connection. Audio goes in through ``send``; events come out of ``events``."""

    session_id: str

    async def send(self, chunk: bytes) -> None: ...

    async def end_of_stream(self) -> None: ...

    def events(self) -> AsyncIterator[SttEvent]: ...

    async def close(self) -> None: ...


class SttEngine(Protocol):
    name: str

    async def open(self, stage: StageConfig) -> SttSession: ...
