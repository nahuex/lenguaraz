# SPDX-License-Identifier: Apache-2.0
"""Spec 001 — AC-9: the shipped stages.yaml + samples work end to end in dry-run mode."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from lenguaraz.api.app import create_app
from lenguaraz.config import Settings, StagesFile
from lenguaraz.models import CaptionEvent, StatusEvent, parse_event

ROOT = Path(__file__).resolve().parents[1]


def test_bundled_config_streams_captions_without_credentials(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(ROOT)  # stages.yaml sources are relative to the repo root
    stages = StagesFile.load(ROOT / "stages.yaml")
    assert [s.id for s in stages.stages] == ["main", "workshop"]
    for stage in stages.stages:
        assert (ROOT / stage.source).is_file(), f"missing bundled sample {stage.source}"
        assert (ROOT / stage.source).with_suffix(".txt").is_file()

    settings = Settings(_env_file=None, engine="fake")
    app = create_app(settings, stages, web_dist=ROOT / "web" / "dist")
    with TestClient(app) as client:
        assert client.get("/healthz").json()["engine"] == "fake"
        assert all(row["dry_run"] for row in client.get("/api/stages").json())
        for stage_id, lang in (("main", "en"), ("workshop", "es")):
            with client.websocket_connect(f"/ws/{stage_id}?lang={lang}") as ws:
                assert isinstance(parse_event(ws.receive_text()), StatusEvent)
                interim = final = None
                deadline = time.monotonic() + 8
                while (interim is None or final is None) and time.monotonic() < deadline:
                    event = parse_event(ws.receive_text())
                    if isinstance(event, CaptionEvent):
                        if event.is_final:
                            final = event
                        else:
                            interim = event
                assert interim is not None and final is not None, stage_id
                assert final.lang == lang and final.text.endswith(".")


def test_translated_captions_flow_for_always_on_and_on_demand_languages(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Spec 002 — AC-8/AC-9: `?lang=es` (always-on) and `?lang=pt` (on demand) on the EN stage."""
    monkeypatch.chdir(ROOT)
    stages = StagesFile.load(ROOT / "stages.yaml")
    settings = Settings(_env_file=None, engine="fake", always_on_langs="es")
    app = create_app(settings, stages, web_dist=ROOT / "web" / "dist")
    with TestClient(app) as client:
        for lang in ("es", "pt"):
            with client.websocket_connect(f"/ws/main?lang={lang}") as ws:
                assert isinstance(parse_event(ws.receive_text()), StatusEvent)
                translated = None
                deadline = time.monotonic() + 10
                while translated is None and time.monotonic() < deadline:
                    event = parse_event(ws.receive_text())
                    if isinstance(event, CaptionEvent) and event.is_final and event.lang == lang:
                        translated = event
                assert translated is not None, lang
                assert translated.text.startswith(f"[{lang}] ")
                assert translated.original and translated.original != translated.text
                assert translated.source_lang == "en" and translated.degraded is False
        rows = {row["id"]: row for row in client.get("/api/stages").json()}
        assert "es" in rows["main"]["active_languages"]
        assert rows["main"]["translation_tokens"]["es"]["calls"] >= 1
