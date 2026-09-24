# SPDX-License-Identifier: Apache-2.0
"""Engine selection from settings (``ENGINE=gemini|fake``)."""

from __future__ import annotations

from lenguaraz.config import EngineKind, Settings
from lenguaraz.stt.base import SttEngine
from lenguaraz.stt.fake import FakeSttEngine


def build_stt_engine(settings: Settings) -> SttEngine:
    if settings.engine is EngineKind.FAKE:
        return FakeSttEngine()
    from lenguaraz.stt.gemini import GeminiSttEngine  # lazy: pulls in the SDK client

    return GeminiSttEngine(settings)
