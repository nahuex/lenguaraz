# SPDX-License-Identifier: Apache-2.0
"""Lengua — live transcription: engine interface, Gemini and fake implementations."""

from lenguaraz.stt.base import SttEngine, SttEvent, SttEventKind, SttSession

__all__ = ["SttEngine", "SttEvent", "SttEventKind", "SttSession"]
