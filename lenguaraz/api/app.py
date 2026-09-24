# SPDX-License-Identifier: Apache-2.0
"""FastAPI application factory: health, stage list, caption WebSocket and the static SPA."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request, WebSocket
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from lenguaraz import __version__
from lenguaraz.api.admin import router as admin_router
from lenguaraz.api.ws import ConnectionLimiter, caption_socket
from lenguaraz.bus.base import Bus
from lenguaraz.bus.memory import MemoryBus
from lenguaraz.config import Settings, StagesFile, load_settings
from lenguaraz.engines import build_auto_glossary, build_stt_engine, build_translation_engine
from lenguaraz.ingest import open_source
from lenguaraz.runner import SourceFactory, StageManager
from lenguaraz.stt.base import SttEngine
from lenguaraz.translate.base import TranslationEngine

log = logging.getLogger("lenguaraz.api")

PLACEHOLDER_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Lenguaraz</title></head><body style="font-family:system-ui;padding:2rem">
<h1>Lenguaraz</h1><p>The API is up, but the audience view is not built yet.</p>
<p>Run <code>cd web &amp;&amp; npm install &amp;&amp; npm run build</code>, or start the dev server
with <code>cd web &amp;&amp; npm run dev</code> and open <a href="http://localhost:5173">http://localhost:5173</a>.</p>
<p>Endpoints: <a href="/healthz">/healthz</a> · <a href="/api/stages">/api/stages</a> ·
<code>ws://…/ws/{stage_id}?lang=</code></p></body></html>"""


def default_web_dist() -> Path:
    return Path(__file__).resolve().parents[2] / "web" / "dist"


def create_app(
    settings: Settings,
    stages: StagesFile | None = None,
    *,
    engine: SttEngine | None = None,
    bus: Bus | None = None,
    source_factory: SourceFactory = open_source,
    metrics_interval: float = 5.0,
    web_dist: Path | None = None,
    translator: TranslationEngine | None = None,
) -> FastAPI:
    stages = stages or StagesFile.load(settings.stages_file)
    engine = engine or build_stt_engine(settings)
    translator = translator or build_translation_engine(settings)
    auto_glossary = build_auto_glossary(settings)
    bus = bus or MemoryBus()
    manager = StageManager(
        stages,
        engine=engine,
        bus=bus,
        settings=settings,
        source_factory=source_factory,
        metrics_interval=metrics_interval,
        translator=translator,
        auto_glossary=auto_glossary,
    )
    dist = web_dist or settings.web_dist or default_web_dist()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        log.info("starting %d stage(s) with engine=%s", len(manager.runners), settings.engine.value)
        await manager.start_all()
        try:
            yield
        finally:
            await manager.stop_all()

    app = FastAPI(title="Lenguaraz", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.manager = manager
    app.state.bus = bus
    limiter = ConnectionLimiter(settings.ws_max_conn_per_ip)

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {
            "status": "ok",
            "engine": settings.engine.value,
            "stages": len(manager.runners),
            "version": __version__,
        }

    @app.get("/api/stages")
    async def list_stages() -> list[dict[str, Any]]:
        return manager.snapshot()

    @app.websocket("/ws/{stage_id}")
    async def ws_captions(
        websocket: WebSocket, stage_id: str, lang: str | None = Query(default=None)
    ) -> None:
        await caption_socket(websocket, stage_id, lang, limiter=limiter)

    app.include_router(admin_router)

    index = dist / "index.html"
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str, request: Request) -> Any:
        if path.startswith(("api/", "ws/")):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        candidate = dist / path
        if path and candidate.is_file() and candidate.resolve().is_relative_to(dist.resolve()):
            return FileResponse(candidate)
        if index.is_file():
            return FileResponse(index)
        return HTMLResponse(PLACEHOLDER_HTML)

    return app


def build() -> FastAPI:
    """Factory for ``uvicorn --factory lenguaraz.api.app:build``."""
    return create_app(load_settings())
