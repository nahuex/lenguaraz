# SPDX-License-Identifier: Apache-2.0
"""Gemini text translation through the Interactions API (plan 002 §2).

Verified surfaces: ``client.aio.interactions.create(model=…, input=…, system_instruction=…,
generation_config={"thinking_level": …, "max_output_tokens": …}, stream=True)`` returning
``step.delta`` events (``delta.type == "text"``) and ``interaction.completed`` with usage.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from google.genai import errors

from lenguaraz.config import Settings
from lenguaraz.translate.base import (
    DeltaCallback,
    TranslationError,
    TranslationOutcome,
    TranslationRequest,
    TranslationUsage,
)
from lenguaraz.translate.prompt import build_prompt, clean_translation

log = logging.getLogger("lenguaraz.translate.gemini")

RETRYABLE_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


def classify(exc: BaseException) -> TranslationError:
    code = getattr(exc, "code", None)
    message = getattr(exc, "message", None) or str(exc)
    retryable = code is None or code in RETRYABLE_CODES
    if code == 429:
        message = f"quota exhausted (429): {message}"
    return TranslationError(message, code=code, retryable=retryable)


def _usage_from(interaction: Any) -> TranslationUsage:
    usage = getattr(interaction, "usage", None)
    if usage is None:
        return TranslationUsage(calls=1)

    def pick(*names: str) -> int:
        for name in names:
            value = getattr(usage, name, None)
            if isinstance(value, int | float):
                return int(value)
        return 0

    return TranslationUsage(
        input_tokens=pick("input_tokens", "prompt_tokens", "prompt_token_count"),
        output_tokens=pick("output_tokens", "candidates_tokens", "response_token_count"),
        total_tokens=pick("total_tokens", "total_token_count"),
        calls=1,
    )


class GeminiTranslationEngine:
    name = "gemini"

    def __init__(self, settings: Settings, *, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client
        self.last_request_kwargs: dict[str, Any] | None = None

    def client(self) -> Any:
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._settings.api_key())
        return self._client

    async def translate(
        self, request: TranslationRequest, on_delta: DeltaCallback | None = None
    ) -> TranslationOutcome:
        system, prompt = build_prompt(request)
        kwargs: dict[str, Any] = {
            "model": self._settings.gemini_translate_model,
            "input": prompt,
            "system_instruction": system,
            "generation_config": {
                "thinking_level": self._settings.gemini_translate_thinking,
                "max_output_tokens": self._settings.translate_max_output_tokens,
            },
            "stream": True,
        }
        self.last_request_kwargs = kwargs
        started = time.monotonic()
        ttft_ms: int | None = None
        chunks: list[str] = []
        usage = TranslationUsage(calls=1)
        try:
            stream = await self.client().aio.interactions.create(**kwargs)
            async for event in stream:
                kind = getattr(event, "event_type", None)
                if kind == "step.delta":
                    delta = getattr(event, "delta", None)
                    text = getattr(delta, "text", None) if delta is not None else None
                    if getattr(delta, "type", None) == "text" and text:
                        if ttft_ms is None:
                            ttft_ms = round((time.monotonic() - started) * 1000)
                        chunks.append(text)
                        if on_delta is not None:
                            on_delta(text)
                elif kind == "interaction.completed":
                    usage = _usage_from(getattr(event, "interaction", None))
        except errors.APIError as exc:
            raise classify(exc) from exc
        except (ConnectionError, OSError, TimeoutError) as exc:
            raise TranslationError(f"connection lost: {exc}", retryable=True) from exc
        text = clean_translation("".join(chunks))
        if not text:
            raise TranslationError("empty translation", retryable=True)
        return TranslationOutcome(text=text, usage=usage, ttft_ms=ttft_ms)
