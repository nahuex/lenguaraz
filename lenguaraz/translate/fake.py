# SPDX-License-Identifier: Apache-2.0
"""FakeTranslator: deterministic, network-free translation for tests and the dry run."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

from lenguaraz.config import short_code
from lenguaraz.translate.base import (
    DeltaCallback,
    TranslationOutcome,
    TranslationRequest,
    TranslationUsage,
)


class FakeTranslator:
    """Returns ``[<target>] <text>`` so the pipeline is visibly exercised without a model."""

    name = "fake"

    def __init__(self, *, delay: float = 0.0, failures: Iterable[Exception] = ()) -> None:
        self._delay = delay
        self._failures = list(failures)
        self.requests: list[TranslationRequest] = []

    async def translate(
        self, request: TranslationRequest, on_delta: DeltaCallback | None = None
    ) -> TranslationOutcome:
        self.requests.append(request)
        if self._failures:
            raise self._failures.pop(0)
        if self._delay:
            await asyncio.sleep(self._delay)
        if short_code(request.source_lang) == short_code(request.target_lang):
            text = request.text
        else:
            text = f"[{short_code(request.target_lang)}] {request.text}"
        if on_delta is not None:
            on_delta(text)
        usage = TranslationUsage(
            input_tokens=max(1, len(request.text) // 4),
            output_tokens=max(1, len(text) // 4),
            total_tokens=max(2, (len(request.text) + len(text)) // 4),
            calls=1,
        )
        return TranslationOutcome(text=text, usage=usage, ttft_ms=0)
