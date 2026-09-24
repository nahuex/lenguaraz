# SPDX-License-Identifier: Apache-2.0
"""Transcription — live STT: engine interface, Gemini and fake implementations."""

from lenguaraz.stt.base import SttEngine, SttEvent, SttEventKind, SttSession

__all__ = ["SttEngine", "SttEvent", "SttEventKind", "SttSession"]
