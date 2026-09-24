# SPDX-License-Identifier: Apache-2.0
"""Diccionario — the lenguaraz's knowledge: glossary helpers and the auto-glossary."""

from lenguaraz.glossary.auto import (
    AutoGlossary,
    FakeAutoGlossary,
    GeminiAutoGlossary,
    extract_terms_heuristic,
    merge_glossary,
)

__all__ = [
    "AutoGlossary",
    "FakeAutoGlossary",
    "GeminiAutoGlossary",
    "extract_terms_heuristic",
    "merge_glossary",
]
