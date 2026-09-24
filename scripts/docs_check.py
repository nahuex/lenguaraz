# SPDX-License-Identifier: Apache-2.0
"""``make docs-check``: docs are code (Constitution Art. XVII.D.4).

1. Every ``Settings`` field (as its ``ENV_VAR`` name) and every ``StageConfig`` field must
   appear in ``docs/configuration.md``, and every documented key must exist in the code.
2. Every relative Markdown link in README*.md and docs/**/*.md must resolve to a file.
3. The Art. XVII.D.3 documentation set exists and README carries its required sections.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lenguaraz.config import Settings, StageConfig, TalkInfo  # noqa: E402

CONFIG_DOC = ROOT / "docs" / "configuration.md"
# Constitution Art. XVII.D.3 + spec 008 FR-008-01: any conference can deploy it without us.
REQUIRED_DOCS = (
    "README.md",
    "README.es.md",
    "LICENSE",
    "NOTICE",
    "THIRD_PARTY_LICENSES.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "CHANGELOG.md",
    "docs/deploy/quickstart.md",
    "docs/deploy/production.md",
    "docs/deploy/scaling.md",
    "docs/deploy/audio-sources.md",
    "docs/deploy/cloud-run.md",
    "docs/es/quickstart.md",
    "docs/configuration.md",
    "docs/customization.md",
    "docs/cost.md",
    "docs/architecture.md",
    "docs/security.md",
    "docs/privacy.md",
    "docs/troubleshooting.md",
    "docs/metrics.md",
    "docs/operations/runbook.md",
    "docs/devpost.md",
    "docs/video-script.md",
    "examples/stages.minimal.yaml",
    "examples/stages.multitrack.yaml",
    "examples/branding.example.yaml",
    "examples/env/dry-run.env",
    "examples/env/production.env",
)
README_SECTIONS = (
    "## Quickstart",
    "## Scaling",
    "## Security & privacy",
    "## Limitations",
    "## Prior art",
    "## How this repo is built",
    "## Documentation",
    "## License",
)
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
KEY = re.compile(r"^\| `([A-Z][A-Z0-9_]+)` \|", re.MULTILINE)  # first column of the env table


def check_config_keys(problems: list[str]) -> None:
    if not CONFIG_DOC.is_file():
        problems.append(f"missing {CONFIG_DOC.relative_to(ROOT)}")
        return
    text = CONFIG_DOC.read_text(encoding="utf-8")
    env_keys = {name.upper() for name in Settings.model_fields}
    documented = set(KEY.findall(text))
    for key in sorted(env_keys - documented):
        problems.append(f"configuration.md: env var `{key}` is not documented")
    for key in sorted(documented - env_keys):
        problems.append(f"configuration.md: documents `{key}`, which does not exist in Settings")
    stage_keys = set(StageConfig.model_fields) | {f"talk.{f}" for f in TalkInfo.model_fields}
    stage_keys.discard("talk")
    for key in sorted(stage_keys):
        if f"`{key}`" not in text:
            problems.append(f"configuration.md: stages.yaml field `{key}` is not documented")


def check_links(problems: list[str]) -> None:
    files = [*ROOT.glob("README*.md"), *(ROOT / "docs").rglob("*.md")]
    for path in files:
        for target in LINK.findall(path.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            clean = target.split("#", 1)[0]
            if not clean:
                continue
            candidate = (path.parent / clean).resolve()
            if not candidate.exists():
                problems.append(f"{path.relative_to(ROOT)}: broken link → {target}")


def check_required_set(problems: list[str]) -> None:
    for relative in REQUIRED_DOCS:
        if not (ROOT / relative).is_file():
            problems.append(f"required document missing: {relative}")
    readme = ROOT / "README.md"
    if readme.is_file():
        text = readme.read_text(encoding="utf-8")
        for heading in README_SECTIONS:
            if heading not in text:
                problems.append(f"README.md: missing section '{heading}'")


def main() -> int:
    problems: list[str] = []
    check_config_keys(problems)
    check_links(problems)
    check_required_set(problems)
    if problems:
        print("docs-check: FAIL")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("docs-check: OK (config keys documented, links resolve, required set present)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
