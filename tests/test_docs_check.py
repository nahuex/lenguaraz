# SPDX-License-Identifier: Apache-2.0
"""Spec 008 AC-1: docs-check enforces the Art. XVII.D.3 documentation set."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "docs_check.py"
spec = importlib.util.spec_from_file_location("docs_check", SCRIPT)
assert spec and spec.loader
docs_check = importlib.util.module_from_spec(spec)
sys.modules["docs_check"] = docs_check
spec.loader.exec_module(docs_check)


def test_required_set_is_present_in_the_repo() -> None:
    problems: list[str] = []
    docs_check.check_required_set(problems)
    assert problems == []


def test_missing_document_or_section_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "README.md").write_text("# x\n\n## Quickstart\n", encoding="utf-8")
    monkeypatch.setattr(docs_check, "ROOT", tmp_path)
    problems: list[str] = []
    docs_check.check_required_set(problems)
    assert "required document missing: docs/deploy/production.md" in problems
    assert "README.md: missing section '## Prior art'" in problems
    assert not any("'## Quickstart'" in p for p in problems)
