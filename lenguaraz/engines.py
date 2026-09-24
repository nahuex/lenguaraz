# SPDX-License-Identifier: Apache-2.0
"""Engine selection from settings (``ENGINE=gemini|fake``)."""

from __future__ import annotations

from lenguaraz.config import EngineKind, Settings
from lenguaraz.stt.base import SttEngine
from lenguaraz.stt.fake import FakeSttEngine
from lenguaraz.translate.base import TranslationEngine
from lenguaraz.translate.fake import FakeTranslator


def build_stt_engine(settings: Settings) -> SttEngine:
    if settings.engine is EngineKind.FAKE:
        return FakeSttEngine()
    from lenguaraz.stt.gemini import GeminiSttEngine  # lazy: pulls in the SDK client

    return GeminiSttEngine(settings)


def build_translation_engine(settings: Settings) -> TranslationEngine:
    if settings.engine is EngineKind.FAKE:
        return FakeTranslator()
    from lenguaraz.translate.gemini import GeminiTranslationEngine  # lazy: SDK client

    return GeminiTranslationEngine(settings)
