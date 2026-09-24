# SPDX-License-Identifier: Apache-2.0
"""Mangrullo — operator API behind ``ADMIN_TOKEN`` (Bearer). Constitution Art. VIII.2."""

from __future__ import annotations

import hmac
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse

from lenguaraz.export import FORMATS
from lenguaraz.runner import StageManager, StageRunner

router = APIRouter(prefix="/api/admin", tags=["mangrullo"])

MEDIA_TYPES = {"srt": "application/x-subrip", "vtt": "text/vtt", "txt": "text/plain"}


def require_admin(request: Request, authorization: str | None = Header(default=None)) -> None:
    expected = request.app.state.settings.admin_token.get_secret_value()
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token or not hmac.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="invalid or missing admin token")


def _runner(request: Request, stage_id: str) -> StageRunner:
    manager: StageManager = request.app.state.manager
    runner = manager.get(stage_id)
    if runner is None:
        raise HTTPException(status_code=404, detail=f"unknown stage {stage_id!r}")
    return runner


@router.get("/stages", dependencies=[Depends(require_admin)])
async def list_stages(request: Request) -> list[dict[str, Any]]:
    manager: StageManager = request.app.state.manager
    return manager.snapshot()


@router.post("/stages/{stage_id}/start", dependencies=[Depends(require_admin)])
async def start_stage(request: Request, stage_id: str) -> dict[str, Any]:
    runner = _runner(request, stage_id)
    await runner.start()
    return {"id": stage_id, "state": runner.state.value, "running": runner.running}


@router.post("/stages/{stage_id}/stop", dependencies=[Depends(require_admin)])
async def stop_stage(request: Request, stage_id: str) -> dict[str, Any]:
    runner = _runner(request, stage_id)
    await runner.stop()
    return {"id": stage_id, "state": runner.state.value, "running": runner.running}


@router.get("/stages/{stage_id}/export", dependencies=[Depends(require_admin)])
async def export_transcript(
    request: Request,
    stage_id: str,
    format: Literal["srt", "vtt", "txt"] = "srt",
    lang: str | None = None,
) -> PlainTextResponse:
    runner = _runner(request, stage_id)
    store = runner.transcript
    available = store.languages()
    code = (lang or runner.stage.primary_source_lang or (available[0] if available else "")).lower()
    if format not in FORMATS:
        raise HTTPException(status_code=400, detail=f"format must be one of {FORMATS}")
    try:
        body = store.render(code, format)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"no transcript for language {code!r}; available: {available}",
        ) from exc
    filename = f"{stage_id}-{code}.{format}"
    return PlainTextResponse(
        body,
        media_type=MEDIA_TYPES[format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
