# SPDX-License-Identifier: Apache-2.0
"""Spec 001 — FR-001-08, AC-6 (WS contract, close codes), NFR-001-02 (fan-out latency)."""

from __future__ import annotations

import time
import wave
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from lenguaraz.api.app import create_app
from lenguaraz.bus.memory import MemoryBus
from lenguaraz.config import Settings, StageConfig, StagesFile
from lenguaraz.ingest.wav import WavFileSource
from lenguaraz.metrics import percentile
from lenguaraz.models import CaptionEvent, StatusEvent, parse_event
from lenguaraz.stt.fake import FakeSttEngine


def write_wav(path: Path, seconds: float) -> Path:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(bytes(int(16000 * seconds) * 2))
    return path


@pytest.fixture
def bus() -> MemoryBus:
    return MemoryBus()


@pytest.fixture
def client(tmp_path: Path, bus: MemoryBus) -> Iterator[TestClient]:
    wav = write_wav(tmp_path / "talk.wav", 3.0)
    (tmp_path / "talk.txt").write_text(
        "Captions over the socket.\nSecond line here.\n", encoding="utf-8"
    )
    stages = StagesFile(
        stages=[
            StageConfig(
                id="main", name="Main", source=str(wav), source_lang=["en-US"], targets=["es"]
            ),
            StageConfig(id="auto", name="Auto", source=str(wav), source_lang=[], targets=["en"]),
        ]
    )
    app = create_app(
        Settings(_env_file=None, engine="fake", ws_max_conn_per_ip=2),
        stages,
        engine=FakeSttEngine(words_per_second=8),
        bus=bus,
        source_factory=lambda source, **_: WavFileSource(source, realtime=True, loop=True),
        web_dist=tmp_path / "no-dist",
    )
    with TestClient(app) as test_client:
        yield test_client


def test_status_first_then_captions_matching_the_contract(client: TestClient) -> None:
    with client.websocket_connect("/ws/main?lang=en") as ws:
        first = parse_event(ws.receive_text())
        assert isinstance(first, StatusEvent)
        assert first.stage_id == "main"
        captions: list[CaptionEvent] = []
        deadline = time.monotonic() + 5
        while len(captions) < 3 and time.monotonic() < deadline:
            event = parse_event(ws.receive_text())
            if isinstance(event, CaptionEvent):
                captions.append(event)
        assert len(captions) == 3
        assert all(c.lang == "en" and c.source_lang == "en" for c in captions)
        assert captions[0].is_final is False
        assert all(c.seq == captions[0].seq for c in captions)  # same utterance
        ws.send_text("ping")  # tolerated
        ws.send_text("anything else")  # ignored


def test_default_lang_is_the_source_language(client: TestClient) -> None:
    with client.websocket_connect("/ws/main") as ws:
        parse_event(ws.receive_text())
        event = parse_event(ws.receive_text())
        while not isinstance(event, CaptionEvent):
            event = parse_event(ws.receive_text())
        assert event.lang == "en"


def test_unknown_stage_closes_with_4404(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as info, client.websocket_connect("/ws/nope") as ws:
        ws.receive_text()
    assert info.value.code == 4404


def test_unsupported_lang_closes_with_4400(client: TestClient) -> None:
    with (
        pytest.raises(WebSocketDisconnect) as info,
        client.websocket_connect("/ws/main?lang=zz") as ws,
    ):
        ws.receive_text()
    assert info.value.code == 4400


def test_auto_detect_stage_accepts_any_short_code(client: TestClient) -> None:
    with client.websocket_connect("/ws/auto?lang=pt") as ws:
        assert isinstance(parse_event(ws.receive_text()), StatusEvent)


def test_per_ip_connection_limit_closes_with_4429(client: TestClient) -> None:
    with client.websocket_connect("/ws/main") as a, client.websocket_connect("/ws/main") as b:
        a.receive_text()
        b.receive_text()
        with pytest.raises(WebSocketDisconnect) as info, client.websocket_connect("/ws/main") as c:
            c.receive_text()
        assert info.value.code == 4429
    # slots are released on disconnect
    with client.websocket_connect("/ws/main") as d:
        d.receive_text()


def test_listener_count_is_visible_in_api(client: TestClient) -> None:
    with client.websocket_connect("/ws/main?lang=es") as ws:
        ws.receive_text()
        rows = {row["id"]: row for row in client.get("/api/stages").json()}
        assert rows["main"]["listeners"] == 1
    rows = {row["id"]: row for row in client.get("/api/stages").json()}
    assert rows["main"]["listeners"] == 0


def test_fanout_latency_bus_to_socket(client: TestClient, bus: MemoryBus) -> None:
    with client.websocket_connect("/ws/main?lang=en") as ws:
        ws.receive_text()
        latencies: list[int] = []
        for seq in range(50):
            sent = time.perf_counter()
            bus.publish(
                "main",
                CaptionEvent(
                    stage_id="main",
                    seq=10_000 + seq,
                    lang="en",
                    source_lang="en",
                    is_final=True,
                    text=f"probe {seq}",
                    t_audio_ms=0,
                    latency_ms=0,
                ),
            )
            while True:
                event = parse_event(ws.receive_text())
                if isinstance(event, CaptionEvent) and event.seq == 10_000 + seq:
                    latencies.append(int((time.perf_counter() - sent) * 1000))
                    break
        assert percentile(latencies, 95) <= 150
