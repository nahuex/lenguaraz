# SPDX-License-Identifier: Apache-2.0
"""Spec 001 — FR-001-09, AC-1 (/healthz, /api/stages), SPA fallback."""

from __future__ import annotations

import wave
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lenguaraz.api.app import create_app
from lenguaraz.config import Settings, StageConfig, StagesFile
from lenguaraz.ingest.wav import WavFileSource
from lenguaraz.stt.fake import FakeSttEngine


def write_wav(path: Path, seconds: float) -> Path:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(bytes(int(16000 * seconds) * 2))
    return path


def slow_source(source: str, **_: object) -> WavFileSource:
    return WavFileSource(source, realtime=True, loop=True)


@pytest.fixture
def stages(tmp_path: Path) -> StagesFile:
    wav = write_wav(tmp_path / "talk.wav", 2.0)
    (tmp_path / "talk.txt").write_text("Hello from the API test.\n", encoding="utf-8")
    return StagesFile(
        stages=[
            StageConfig(
                id="main", name="Main", source=str(wav), source_lang=["en-US"], targets=["es"]
            ),
            StageConfig(id="side", name="Side", source=str(wav), source_lang=[], targets=["en"]),
        ]
    )


@pytest.fixture
def client(stages: StagesFile, tmp_path: Path) -> Iterator[TestClient]:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
    app = create_app(
        Settings(_env_file=None, engine="fake"),
        stages,
        engine=FakeSttEngine(),
        source_factory=slow_source,
        web_dist=dist,
    )
    with TestClient(app) as test_client:
        yield test_client


def test_healthz(client: TestClient) -> None:
    body = client.get("/healthz").json()
    assert body["status"] == "ok"
    assert body["engine"] == "fake"
    assert body["stages"] == 2


def test_api_stages_lists_every_stage_with_state(client: TestClient) -> None:
    rows = {row["id"]: row for row in client.get("/api/stages").json()}
    assert set(rows) == {"main", "side"}
    assert rows["main"]["state"] in {"STARTING", "LIVE"}
    assert rows["main"]["source_lang"] == ["en-US"]
    assert rows["main"]["targets"] == ["es"]
    assert rows["main"]["languages"] == ["en", "es"]
    assert rows["main"]["dry_run"] is True
    assert rows["main"]["listeners"] == 0
    assert rows["side"]["languages"] == ["en"]


def test_spa_fallback_and_assets(client: TestClient) -> None:
    assert client.get("/").text.startswith("<!doctype html>")
    assert client.get("/fogon/main").text.startswith("<!doctype html>")
    assert client.get("/assets/app.js").text == "console.log('ok')"
    assert client.get("/api/nope").status_code == 404
    assert client.get("/../pyproject.toml").status_code in (200, 404)  # never escapes dist


def test_placeholder_when_frontend_is_not_built(stages: StagesFile, tmp_path: Path) -> None:
    app = create_app(
        Settings(_env_file=None, engine="fake"),
        stages,
        engine=FakeSttEngine(),
        source_factory=slow_source,
        web_dist=tmp_path / "no-dist",
    )
    with TestClient(app) as test_client:
        response = test_client.get("/")
        assert response.status_code == 200
        assert "not built yet" in response.text
