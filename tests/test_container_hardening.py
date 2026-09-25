# SPDX-License-Identifier: Apache-2.0
"""Spec 007 AC-4: the container runs non-root, read-only, with a healthcheck.

Spec 013 AC-3: the ``tls`` Compose profile adds Caddy with the Caddyfile mounted and keeps
Lenguaraz's host port on loopback.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ROOT / "docker-compose.yml"
CADDYFILE = ROOT / "deploy" / "Caddyfile"


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
    entries = env_file if isinstance(env_file, list) else [env_file]
    assert ".env" in [e["path"] if isinstance(e, dict) else e for e in entries]


def test_tls_profile() -> None:
    """AC-3 (spec 013): Caddy behind the ``tls`` profile; Lenguaraz published on loopback only."""
    data = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    lenguaraz = data["services"]["lenguaraz"]
    assert lenguaraz["ports"] == ["127.0.0.1:8000:8000"]
    caddy = data["services"]["caddy"]
    assert caddy["profiles"] == ["tls"]
    assert caddy["image"].startswith("caddy:")
    assert "./deploy/Caddyfile:/etc/caddy/Caddyfile:ro" in caddy["volumes"]
    assert {"80:80", "443:443"} <= set(caddy["ports"])
    assert "lenguaraz" in caddy["depends_on"]
    assert caddy["restart"] == "unless-stopped"
    assert {"caddy_data", "caddy_config"} <= set(data["volumes"])
    caddyfile = CADDYFILE.read_text(encoding="utf-8")
    assert caddyfile.splitlines()[0].startswith("# SPDX-License-Identifier: Apache-2.0")
    assert "reverse_proxy lenguaraz:8000" in caddyfile
    assert "Strict-Transport-Security" in caddyfile
    assert "email {$ACME_EMAIL}" in caddyfile
    assert "{$DOMAIN}" in caddyfile
    # Caddy rejects an empty "email": Compose must always hand it a value.
    assert caddy["environment"]["ACME_EMAIL"].startswith("${ACME_EMAIL:-admin@")
    assert "certs/" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_tls_profile_renders_with_docker_compose(tmp_path: Path) -> None:
    """The same check through ``docker compose --profile tls config`` when Docker is installed."""
    if shutil.which("docker") is None:
        pytest.skip("docker is not installed")
    try:
        probe = subprocess.run(
            ["docker", "compose", "version"], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        pytest.skip("docker compose is not available")
    if probe.returncode != 0:
        pytest.skip("docker compose is not available")
    # A copy without any .env: the profile must render from defaults plus DOMAIN/ACME_EMAIL.
    shutil.copy(COMPOSE, tmp_path / "docker-compose.yml")
    (tmp_path / "deploy").mkdir()
    shutil.copy(CADDYFILE, tmp_path / "deploy" / "Caddyfile")
    env = {**os.environ, "DOMAIN": "captions.example.org", "ACME_EMAIL": "ops@example.org"}
    rendered = subprocess.run(
        ["docker", "compose", "--profile", "tls", "config", "--format", "json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert rendered.returncode == 0, rendered.stderr
    services = json.loads(rendered.stdout)["services"]
    caddy = services["caddy"]
    assert caddy["environment"]["DOMAIN"] == "captions.example.org"
    assert caddy["environment"]["ACME_EMAIL"] == "ops@example.org"
    defaults = subprocess.run(
        ["docker", "compose", "--profile", "tls", "config", "--format", "json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={k: v for k, v in os.environ.items() if k not in {"DOMAIN", "ACME_EMAIL"}},
        timeout=60,
    )
    assert defaults.returncode == 0, defaults.stderr
    caddy_defaults = json.loads(defaults.stdout)["services"]["caddy"]["environment"]
    assert caddy_defaults == {"DOMAIN": "localhost", "ACME_EMAIL": "admin@localhost"}
    assert any(
        volume.get("target") == "/etc/caddy/Caddyfile" and volume.get("read_only") is True
        for volume in caddy["volumes"]
    )
    assert {str(p["published"]) for p in caddy["ports"]} == {"80", "443"}
    assert all(p.get("host_ip") == "127.0.0.1" for p in services["lenguaraz"]["ports"])
    without_profile = subprocess.run(
        ["docker", "compose", "config", "--services"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert without_profile.returncode == 0, without_profile.stderr
    assert without_profile.stdout.split() == ["lenguaraz"]


def test_security_policy_present() -> None:
    text = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    for heading in ("Supported versions", "Reporting a vulnerability", "Threat model", "Hardening"):
        assert heading in text
