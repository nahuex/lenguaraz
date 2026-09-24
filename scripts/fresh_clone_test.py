# SPDX-License-Identifier: Apache-2.0
"""Fresh-clone test (Constitution Art. XVII.D.5): clone the public repo into an empty temp
directory, follow the quickstart in dry-run mode, reach /healthz and see captions flow.

Usage: uv run python scripts/fresh_clone_test.py [--repo URL] [--mode auto|docker|local]
                                                 [--port 8765] [--keep]
Docker Compose is used when available (the documented 3-command path); otherwise the
developer path (uv + npm). Exit code 0 = the quickstart works from a clean clone.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_REPO = "https://github.com/nahuex/lenguaraz.git"
HEALTH_TIMEOUT_S = 300
CAPTION_WAIT_S = 15


def log(message: str) -> None:
    print(f"[fresh-clone] {message}", flush=True)


def run(cmd: list[str], cwd: Path, *, timeout: int = 900) -> None:
    log("$ " + " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True, timeout=timeout)


def http_get(url: str, token: str | None = None, timeout: float = 5.0) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def wait_for_health(base: str, timeout_s: float) -> dict[str, object]:
    deadline = time.monotonic() + timeout_s
    last = "no answer yet"
    while time.monotonic() < deadline:
        try:
            status, body = http_get(f"{base}/healthz")
            if status == 200:
                payload = json.loads(body)
                if payload.get("status") == "ok":
                    return payload
            last = f"{status} {body[:80]}"
        except (OSError, ValueError) as exc:
            last = str(exc)
        time.sleep(2)
    raise SystemExit(f"/healthz never answered ok within {timeout_s:.0f}s (last: {last})")


def check_captions(base: str, token: str) -> tuple[str, int]:
    status, body = http_get(f"{base}/api/stages")
    if status != 200:
        raise SystemExit(f"/api/stages returned {status}: {body[:200]}")
    stages = json.loads(body)
    if not stages:
        raise SystemExit("no stages configured")
    if not stages[0].get("dry_run"):
        raise SystemExit("the stage is not in dry-run mode; refusing to spend quota")
    stage_id = stages[0]["id"]
    log(f"stage '{stage_id}' is {stages[0]['state']}; waiting {CAPTION_WAIT_S}s for captions")
    time.sleep(CAPTION_WAIT_S)
    status, body = http_get(f"{base}/api/admin/stages/{stage_id}/export?format=txt", token)
    if status != 200:
        raise SystemExit(f"transcript export returned {status}: {body[:200]}")
    lines = [line for line in body.splitlines() if line.strip()]
    if not lines:
        raise SystemExit("no captions were recorded: the audience view would be empty")
    return stage_id, len(lines)


def docker_available() -> bool:
    try:
        subprocess.run(
            ["docker", "compose", "version"], check=True, capture_output=True, timeout=30
        )
        return True
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def write_env(clone: Path, port: int, token: str) -> None:
    # Exactly what the quickstart says: copy the example, set ENGINE=fake.
    example = (clone / ".env.example").read_text(encoding="utf-8")
    lines = [
        line
        for line in example.splitlines()
        if not line.startswith(("ENGINE=", "ADMIN_TOKEN=", "PORT="))
    ]
    lines += ["ENGINE=fake", f"ADMIN_TOKEN={token}", f"PORT={port}"]
    (clone / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")


def with_docker(clone: Path, port: int, token: str) -> tuple[str, int]:
    project = f"lenguaraz-fresh-{secrets.token_hex(3)}"
    env = {**os.environ, "COMPOSE_PROJECT_NAME": project}
    override = clone / "docker-compose.override.yml"
    override.write_text(
        f'services:\n  lenguaraz:\n    ports: !override\n      - "{port}:8000"\n', encoding="utf-8"
    )
    log("$ docker compose up --build -d")
    subprocess.run(
        ["docker", "compose", "up", "--build", "-d"], cwd=clone, check=True, env=env, timeout=1200
    )
    try:
        base = f"http://127.0.0.1:{port}"
        health = wait_for_health(base, HEALTH_TIMEOUT_S)
        log(f"healthz: {json.dumps(health)}")
        if health.get("engine") != "fake":
            raise SystemExit("engine is not fake")
        return check_captions(base, token)
    finally:
        subprocess.run(
            ["docker", "compose", "down", "-v", "--remove-orphans"], cwd=clone, env=env, timeout=300
        )


def with_local(clone: Path, port: int, token: str) -> tuple[str, int]:
    run(["uv", "sync"], clone)
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    run([npm, "ci", "--prefix", "web"], clone)
    run([npm, "run", "build", "--prefix", "web"], clone)
    log(f"$ uv run lenguaraz serve --host 127.0.0.1 --port {port}")
    server = subprocess.Popen(
        ["uv", "run", "lenguaraz", "serve", "--host", "127.0.0.1", "--port", str(port)], cwd=clone
    )
    try:
        base = f"http://127.0.0.1:{port}"
        health = wait_for_health(base, 120)
        log(f"healthz: {json.dumps(health)}")
        if health.get("engine") != "fake":
            raise SystemExit("engine is not fake")
        return check_captions(base, token)
    finally:
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fresh-clone-test")
    parser.add_argument("--repo", default=os.environ.get("FRESH_CLONE_REPO", DEFAULT_REPO))
    parser.add_argument("--mode", choices=["auto", "docker", "local"], default="auto")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--keep", action="store_true", help="keep the temp clone for inspection")
    args = parser.parse_args(argv)

    mode = args.mode
    if mode == "auto":
        mode = "docker" if docker_available() else "local"
    log(f"repo={args.repo} mode={mode} port={args.port}")

    temp = Path(tempfile.mkdtemp(prefix="lenguaraz-fresh-"))
    clone = temp / "lenguaraz"
    started = time.monotonic()
    try:
        run(["git", "clone", "--depth", "1", args.repo, str(clone)], temp)
        token = secrets.token_hex(16)
        write_env(clone, args.port, token)
        stage_id, lines = (with_docker if mode == "docker" else with_local)(clone, args.port, token)
        elapsed = time.monotonic() - started
        log(f"PASS: stage '{stage_id}' produced {lines} transcript line(s) in dry-run mode")
        log(f"took {elapsed:.0f}s ({mode})")
        return 0
    finally:
        if args.keep:
            log(f"clone kept at {clone}")
        else:
            shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
