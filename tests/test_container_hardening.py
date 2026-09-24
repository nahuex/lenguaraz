# SPDX-License-Identifier: Apache-2.0
"""Spec 007 AC-4: the container runs non-root, read-only, with a healthcheck."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_dockerfile_runs_as_non_root_with_healthcheck() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    users = re.findall(r"^USER\s+(\S+)", text, flags=re.MULTILINE)
    assert users, "no USER instruction"
    assert users[-1] not in {"root", "0"}
    assert re.search(r"^HEALTHCHECK\b", text, flags=re.MULTILINE)
    assert "SPDX-License-Identifier: Apache-2.0" in text.splitlines()[0]


def test_compose_is_read_only_with_healthcheck() -> None:
    data = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    service = data["services"]["lenguaraz"]
    assert service.get("read_only") is True
    assert "no-new-privileges:true" in service.get("security_opt", [])
    assert "/tmp" in service.get("tmpfs", [])
    # the healthcheck comes from the image (Dockerfile HEALTHCHECK) and must not be disabled
    assert service.get("healthcheck", {}).get("disable") is not True
    assert "healthz" in (ROOT / "Dockerfile").read_text(encoding="utf-8")
    env_file = service.get("env_file", [])
    assert ".env" in (env_file if isinstance(env_file, list) else [env_file])


def test_security_policy_present() -> None:
    text = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    for heading in ("Supported versions", "Reporting a vulnerability", "Threat model", "Hardening"):
        assert heading in text
