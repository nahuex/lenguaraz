# SPDX-License-Identifier: Apache-2.0
"""Spec 004 — FR-004-02/03, AC-3 (401), AC-4 (list/start/stop), AC-5 (export)."""

from __future__ import annotations

import time
import wave
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lenguaraz.api.app import create_app
from lenguaraz.config import Settings, StageConfig, StagesFile
from lenguaraz.ingest.wav import WavFileSource
from lenguaraz.stt.fake import FakeSttEngine

TOKEN = "secret-token-for-tests"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def write_wav(path: Path, seconds: float) -> Path:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(bytes(int(16000 * seconds) * 2))
    return path


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    wav = write_wav(tmp_path / "talk.wav", 3.0)
    (tmp_path / "talk.txt").write_text(
        "Hello from the admin test.\nSecond line.\n", encoding="utf-8"
    )
    stages = StagesFile(
        stages=[
            StageConfig(
                id="main", name="Main", source=str(wav), source_lang=["en-US"], targets=["es"]
            ),
            StageConfig(
                id="side", name="Side", source=str(wav), source_lang=["es-419"], targets=["en"]
            ),
        ]
    )
    app = create_app(
        Settings(_env_file=None, engine="fake", admin_token=TOKEN, always_on_langs="es"),
        stages,
        engine=FakeSttEngine(words_per_second=12),
        source_factory=lambda source, **_: WavFileSource(source, realtime=True, loop=True),
        web_dist=tmp_path / "no-dist",
    )
    with TestClient(app) as test_client:
        yield test_client


def test_admin_routes_require_the_bearer_token(client: TestClient) -> None:
    assert client.get("/api/admin/stages").status_code == 401
    assert (
        client.get("/api/admin/stages", headers={"Authorization": "Bearer nope"}).status_code == 401
    )
    assert client.post("/api/admin/stages/main/stop").status_code == 401
    assert client.get("/api/admin/stages/main/export?lang=en").status_code == 401
    assert client.get("/api/admin/stages").json()["detail"] == "invalid or missing admin token"


def test_list_start_stop(client: TestClient) -> None:
    rows = {row["id"]: row for row in client.get("/api/admin/stages", headers=AUTH).json()}
    assert set(rows) == {"main", "side"}
    main = rows["main"]
    assert main["running"] is True
    assert main["est_cost_usd"] >= 0 and main["audio_seconds"] >= 0
    assert isinstance(main["transcript_entries"], dict)
    assert "active_languages" in main and "translation_tokens" in main

    stopped = client.post("/api/admin/stages/side/stop", headers=AUTH).json()
    assert stopped == {"id": "side", "state": "STOPPED", "running": False}
    rows = {row["id"]: row for row in client.get("/api/admin/stages", headers=AUTH).json()}
    assert rows["side"]["running"] is False and rows["main"]["running"] is True

    started = client.post("/api/admin/stages/side/start", headers=AUTH).json()
    assert started["running"] is True
    assert client.post("/api/admin/stages/nope/start", headers=AUTH).status_code == 404


def test_export_srt_vtt_txt_for_original_and_translated_captions(client: TestClient) -> None:
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        rows = {row["id"]: row for row in client.get("/api/admin/stages", headers=AUTH).json()}
        counts = rows["main"]["transcript_entries"]
        if counts.get("en", 0) >= 1 and counts.get("es", 0) >= 1:
            break
        time.sleep(0.2)
    else:
        pytest.fail(f"no transcript entries recorded: {counts}")

    srt = client.get("/api/admin/stages/main/export?format=srt&lang=es", headers=AUTH)
    assert srt.status_code == 200
    assert srt.headers["content-disposition"] == 'attachment; filename="main-es.srt"'
    assert srt.text.startswith("1\n00:00:0")
    assert "[es] Hello from the admin test." in srt.text
    vtt = client.get(
        "/api/admin/stages/main/export?format=vtt", headers=AUTH
    )  # default: source lang
    assert vtt.text.startswith("WEBVTT") and "Hello from the admin test." in vtt.text
    txt = client.get("/api/admin/stages/main/export?format=txt&lang=en", headers=AUTH)
    assert txt.text.startswith("[00:00:0")
    missing = client.get("/api/admin/stages/main/export?format=srt&lang=pt", headers=AUTH)
    assert missing.status_code == 404 and "available" in missing.json()["detail"]
    assert client.get("/api/admin/stages/main/export?format=docx", headers=AUTH).status_code == 422
