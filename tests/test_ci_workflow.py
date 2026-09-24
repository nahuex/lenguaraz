# SPDX-License-Identifier: Apache-2.0
"""Spec 007 AC-2: the CI workflow carries every gate required by FR-007-02."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def steps_text(job: dict) -> str:
    return "\n".join(
        str(step.get("run", "")) + " " + str(step.get("uses", "")) for step in job["steps"]
    )


def test_ci_workflow_has_every_gate() -> None:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert data["env"]["ENGINE"] == "fake"
    triggers = data[True] if True in data else data["on"]  # PyYAML parses `on:` as True
    assert "push" in triggers and "pull_request" in triggers
    jobs = data["jobs"]
    python = steps_text(jobs["python"])
    for needle in (
        "ruff check",
        "ruff format --check",
        "mypy",
        "pytest",
        "spdx_check.sh",
        "docs_check.py",
        "license_check.py --write",
        "THIRD_PARTY_LICENSES.md",
    ):
        assert needle in python, needle
    web = steps_text(jobs["web"])
    assert "npm ci" in web and "npm test" in web and "npm run build" in web
    secrets = jobs["secrets"]
    assert any(s.get("with", {}).get("fetch-depth") == 0 for s in secrets["steps"])
    assert "gitleaks/gitleaks-action" in steps_text(secrets)
    trivy_fs = next(s for s in jobs["trivy-fs"]["steps"] if "trivy-action" in s.get("uses", ""))
    assert trivy_fs["with"]["scan-type"] == "fs" and trivy_fs["with"]["exit-code"] == "1"
    image = steps_text(jobs["image"])
    assert "docker build" in image and "trivy-action" in image and "sbom-action" in image
    image_scan = next(s for s in jobs["image"]["steps"] if "trivy-action" in s.get("uses", ""))
    assert image_scan["with"]["scan-type"] == "image"
    sbom = next(s for s in jobs["image"]["steps"] if "sbom-action" in s.get("uses", ""))
    assert sbom["with"]["format"] == "spdx-json"
    assert all("GEMINI_API_KEY" not in steps_text(job) for job in jobs.values())


def test_dependabot_covers_every_ecosystem() -> None:
    data = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    ecosystems = {u["package-ecosystem"] for u in data["updates"]}
    assert ecosystems == {"pip", "npm", "github-actions", "docker"}
