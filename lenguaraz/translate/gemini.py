# SPDX-License-Identifier: Apache-2.0
"""Gemini text translation (plan 002 §2), with two verified transports.

- ``generate_content`` (default): ``client.aio.models.generate_content_stream(model=…,
  contents=…, config=GenerateContentConfig(system_instruction=…, thinking_config=…,
  max_output_tokens=…))``; chunks carry ``.text`` and the last one ``.usage_metadata``.
  Measured 2026-09-24 on ``gemini-3.5-flash-lite``: time to first token median 578 ms
  versus 1407 ms through the Interactions API (docs/decisions.md D-002-1).
- ``interactions``: ``client.aio.interactions.create(model=…, input=…, system_instruction=…,
  generation_config={"thinking_level": …, "max_output_tokens": …}, stream=True, store=False)``
  returning ``step.delta`` events (``delta.type == "text"``) and ``interaction.completed``
  with ``interaction.usage`` (``total_input_tokens``, ``total_output_tokens``, ``total_tokens``).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from google.genai import errors, types

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


def _pick(obj: Any, *names: str) -> int:
    for name in names:
        value = getattr(obj, name, None)
        if isinstance(value, int | float):
            return int(value)
    return 0


def _usage_from_interaction(interaction: Any) -> TranslationUsage:
    usage = getattr(interaction, "usage", None)
    if usage is None:
        return TranslationUsage(calls=1)
    return TranslationUsage(
        input_tokens=_pick(usage, "total_input_tokens", "input_tokens", "prompt_token_count"),
        output_tokens=_pick(
            usage, "total_output_tokens", "output_tokens", "candidates_token_count"
        ),
        total_tokens=_pick(usage, "total_tokens", "total_token_count"),
        calls=1,
    )


def _usage_from_metadata(metadata: Any) -> TranslationUsage:
    if metadata is None:
        return TranslationUsage(calls=1)
    return TranslationUsage(
        input_tokens=_pick(metadata, "prompt_token_count"),
        output_tokens=_pick(metadata, "candidates_token_count"),
        total_tokens=_pick(metadata, "total_token_count"),
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
        started = time.monotonic()
        chunks: list[str] = []
        ttft: list[int] = []

        def deliver(text: str) -> None:
            if not ttft:
                ttft.append(round((time.monotonic() - started) * 1000))
            chunks.append(text)
            if on_delta is not None:
                on_delta(text)

        try:
            if self._settings.gemini_translate_api == "interactions":
                usage = await self._via_interactions(system, prompt, deliver)
            else:
                usage = await self._via_generate_content(system, prompt, deliver)
        except errors.APIError as exc:
            raise classify(exc) from exc
        except (ConnectionError, OSError, TimeoutError) as exc:
            raise TranslationError(f"connection lost: {exc}", retryable=True) from exc
        text = clean_translation("".join(chunks))
        if not text:
            raise TranslationError("empty translation", retryable=True)
        return TranslationOutcome(text=text, usage=usage, ttft_ms=ttft[0] if ttft else None)

    async def _via_generate_content(
        self, system: str, prompt: str, deliver: DeltaCallback
    ) -> TranslationUsage:
        kwargs: dict[str, Any] = {
            "model": self._settings.gemini_translate_model,
            "contents": prompt,
            "config": types.GenerateContentConfig(
                system_instruction=system,
                thinking_config=types.ThinkingConfig(
                    thinking_level=types.ThinkingLevel[
                        self._settings.gemini_translate_thinking.upper()
                    ]
                ),
                max_output_tokens=self._settings.translate_max_output_tokens,
            ),
        }
        self.last_request_kwargs = kwargs
        usage = TranslationUsage(calls=1)
        stream = await self.client().aio.models.generate_content_stream(**kwargs)
        async for chunk in stream:
            text = getattr(chunk, "text", None)
            if text:
                deliver(text)
            metadata = getattr(chunk, "usage_metadata", None)
            if metadata is not None:
                usage = _usage_from_metadata(metadata)
        return usage

    async def _via_interactions(
        self, system: str, prompt: str, deliver: DeltaCallback
    ) -> TranslationUsage:
        kwargs: dict[str, Any] = {
            "model": self._settings.gemini_translate_model,
            "input": prompt,
            "system_instruction": system,
            "generation_config": {
                "thinking_level": self._settings.gemini_translate_thinking,
                "max_output_tokens": self._settings.translate_max_output_tokens,
            },
            "stream": True,
            "store": False,  # nothing to retrieve later; keeps Google-side state out (Art. IX)
        }
        self.last_request_kwargs = kwargs
        usage = TranslationUsage(calls=1)
        stream = await self.client().aio.interactions.create(**kwargs)
        async for event in stream:
            kind = getattr(event, "event_type", None)
            if kind == "step.delta":
                delta = getattr(event, "delta", None)
                text = getattr(delta, "text", None) if delta is not None else None
                if getattr(delta, "type", None) == "text" and text:
                    deliver(text)
            elif kind == "interaction.completed":
                usage = _usage_from_interaction(getattr(event, "interaction", None))
        return usage
