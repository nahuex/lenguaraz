# SPDX-License-Identifier: Apache-2.0
"""Public caption WebSocket: ``/ws/{stage_id}?lang=``.

Read-only for the audience (Art. VIII.2): the only accepted client message is ``ping``.
Per-IP concurrent-connection limit (Art. VIII.3). Events are JSON, one per message.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from collections import Counter

from fastapi import WebSocket, WebSocketDisconnect

from lenguaraz.bus.base import Subscription
from lenguaraz.bus.memory import SlowConsumerError
from lenguaraz.models import StatusEvent, WsCloseCode
from lenguaraz.runner import StageManager, StageRunner

log = logging.getLogger("lenguaraz.ws")
_SHORT_CODE = re.compile(r"^[a-z]{2,3}$")


class ConnectionLimiter:
    """Counts open sockets per client IP."""

    def __init__(self, max_per_ip: int) -> None:
        self._max = max_per_ip
        self._open: Counter[str] = Counter()

    def acquire(self, ip: str) -> bool:
        if self._open[ip] >= self._max:
            return False
        self._open[ip] += 1
        return True

    def release(self, ip: str) -> None:
        self._open[ip] -= 1
        if self._open[ip] <= 0:
            del self._open[ip]


def resolve_lang(runner: StageRunner, requested: str | None) -> str | None:
    """Pick the language channel for a listener, or None if unsupported."""
    stage = runner.stage
    if not requested:
        return stage.primary_source_lang or (stage.languages() or ["und"])[0]
    requested = requested.lower()
    if requested in stage.languages():
        return requested
    if not stage.source_lang and _SHORT_CODE.match(requested):
        return requested  # auto-detect stage: any detected language may show up
    return None


async def caption_socket(
    websocket: WebSocket, stage_id: str, lang: str | None, *, limiter: ConnectionLimiter
) -> None:
    manager: StageManager = websocket.app.state.manager
    await websocket.accept()
    runner = manager.get(stage_id)
    if runner is None:
        await websocket.close(code=WsCloseCode.UNKNOWN_STAGE, reason="unknown stage")
        return
    channel = resolve_lang(runner, lang)
    if channel is None:
        await websocket.close(code=WsCloseCode.UNSUPPORTED_LANG, reason="unsupported lang")
        return
    ip = websocket.client.host if websocket.client else "unknown"
    if not limiter.acquire(ip):
        await websocket.close(code=WsCloseCode.RATE_LIMITED, reason="too many connections")
        return

    sub: Subscription = manager.bus.subscribe(stage_id, channel)
    extra = {"stage_id": stage_id, "component": "Chasque", "lang": channel}
    log.info("listener connected from %s", ip, extra=extra)
    try:
        await websocket.send_text(
            StatusEvent(
                stage_id=stage_id, state=runner.state, detail=runner.detail
            ).model_dump_json()
        )
        sender = asyncio.create_task(_forward(websocket, sub))
        receiver = asyncio.create_task(_drain_client(websocket))
        done, pending = await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        for task in done:
            exc = task.exception()
            if isinstance(exc, SlowConsumerError):
                with contextlib.suppress(Exception):
                    await websocket.close(code=WsCloseCode.SLOW_CONSUMER, reason="too slow")
            elif exc is not None and not isinstance(exc, WebSocketDisconnect):
                log.warning("listener error: %s", exc, extra=extra)
    finally:
        sub.close()
        limiter.release(ip)
        log.info("listener disconnected", extra=extra)


async def _forward(websocket: WebSocket, sub: Subscription) -> None:
    async for event in sub:
        await websocket.send_text(event.model_dump_json())


async def _drain_client(websocket: WebSocket) -> None:
    async for message in websocket.iter_text():
        if message == "ping":
            continue
        # Anything else is ignored: the audience socket is read-only.
