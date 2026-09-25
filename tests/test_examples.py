# SPDX-License-Identifier: Apache-2.0
"""Every shipped stages example must load (Constitution Art. XVII.D.4: docs are code)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lenguaraz.config import StagesFile

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = [*sorted((ROOT / "examples").glob("stages.*.yaml")), ROOT / "stages.yaml"]


@pytest.mark.parametrize("path", EXAMPLES, ids=[p.name for p in EXAMPLES])
def test_stages_example_loads(path: Path) -> None:
    stages = StagesFile.load(path)
    assert stages.stages, path
    for stage in stages.stages:
        assert stage.id and stage.source and stage.targets is not None
