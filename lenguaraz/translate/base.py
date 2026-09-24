# SPDX-License-Identifier: Apache-2.0
"""Translation engine interface (Constitution Art. XIII.1: the second explicit interface)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

DeltaCallback = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class TranslationRequest:
    text: str
    source_lang: str
    target_lang: str
    glossary: tuple[str, ...] = ()
    context: tuple[tuple[str, str], ...] = ()  # (source segment, its translation), oldest first
    talk_title: str = ""
    talk_abstract: str = ""


@dataclass(slots=True)
class TranslationUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0

    def add(self, other: TranslationUsage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.total_tokens += other.total_tokens
        self.calls += other.calls

    def as_dict(self) -> dict[str, int]:
        return {
            "input": self.input_tokens,
            "output": self.output_tokens,
            "total": self.total_tokens,
            "calls": self.calls,
        }


@dataclass(frozen=True, slots=True)
class TranslationOutcome:
    text: str
    usage: TranslationUsage
    ttft_ms: int | None = None  # time to first streamed token, when known


class TranslationError(Exception):
    def __init__(self, message: str, *, code: int | None = None, retryable: bool = True) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class TranslationEngine(Protocol):
    name: str

    async def translate(
        self, request: TranslationRequest, on_delta: DeltaCallback | None = None
    ) -> TranslationOutcome: ...
