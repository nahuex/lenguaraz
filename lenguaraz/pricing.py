# SPDX-License-Identifier: Apache-2.0
"""Cost estimates from measured usage (Constitution Art. VII.3).

Prices per 1M tokens, USD, read from ai.google.dev/gemini-api/docs/pricing on
``PRICING_DATE`` (ground truth GT-6). Audio input is 25 tokens per second (GT-6.1).
"""

from __future__ import annotations

from collections.abc import Mapping

PRICING_DATE = "2026-09-22"
AUDIO_TOKENS_PER_SECOND = 25
STT_INPUT_PER_M = 3.50  # gemini-3.5-transcribe-live audio input
STT_OUTPUT_PER_M = 21.0  # gemini-3.5-transcribe-live text output
TRANSLATE_INPUT_PER_M = 0.30  # gemini-3.5-flash-lite
TRANSLATE_OUTPUT_PER_M = 2.50


def stt_cost(audio_seconds: float, response_tokens: int = 0, response_chars: int = 0) -> float:
    """Transcription cost; output tokens are estimated from characters when not reported."""
    output_tokens = response_tokens or response_chars / 4
    audio = audio_seconds * AUDIO_TOKENS_PER_SECOND / 1e6 * STT_INPUT_PER_M
    return audio + output_tokens / 1e6 * STT_OUTPUT_PER_M


def translation_cost(usage: Mapping[str, Mapping[str, int]]) -> float:
    total = 0.0
    for tokens in usage.values():
        total += tokens.get("input", 0) / 1e6 * TRANSLATE_INPUT_PER_M
        total += tokens.get("output", 0) / 1e6 * TRANSLATE_OUTPUT_PER_M
    return total


def estimate_stage_cost(
    audio_seconds: float,
    *,
    stt_response_tokens: int = 0,
    stt_response_chars: int = 0,
    translation_usage: Mapping[str, Mapping[str, int]] | None = None,
) -> float:
    return stt_cost(audio_seconds, stt_response_tokens, stt_response_chars) + translation_cost(
        translation_usage or {}
    )
