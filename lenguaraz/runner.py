# SPDX-License-Identifier: Apache-2.0
"""StageRunner and StageManager: one isolated pipeline per stage.

source → queue → ManagedSttSession → bus, plus a metrics ticker. A failure inside one
runner becomes that stage's DEGRADED/STOPPED state and never touches another stage
(Constitution Art. VI.3-4).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from typing import Any

from lenguaraz.bus.base import Bus
from lenguaraz.config import Settings, StageConfig, StagesFile, short_code
from lenguaraz.ingest import AudioSource, IngestError, open_source
from lenguaraz.metrics import StageMetrics
from lenguaraz.models import CaptionEvent, MetricsEvent, StageState, StatusEvent
from lenguaraz.stt.base import SttEngine
from lenguaraz.stt.session import ManagedSttSession, Segment

log = logging.getLogger("lenguaraz.runner")

SourceFactory = Callable[..., AudioSource]
QUEUE_CHUNKS = 50  # 5 s of audio buffered between ingest and the STT session


class StageRunner:
    def __init__(
        self,
        stage: StageConfig,
        *,
        engine: SttEngine,
        bus: Bus,
        settings: Settings,
        source_factory: SourceFactory = open_source,
        metrics_interval: float = 5.0,
    ) -> None:
        self.stage = stage
        self._engine = engine
        self._bus = bus
        self._settings = settings
        self._source_factory = source_factory
        self._metrics_interval = metrics_interval
        self.metrics = StageMetrics()
        self.state = StageState.IDLE
        self.detail: str | None = None
        self.session: ManagedSttSession | None = None
        self._task: asyncio.Task[None] | None = None
        self._source_error: str | None = None
        self._log = logging.LoggerAdapter(log, {"stage_id": stage.id, "component": "Oído/Lengua"})

    # -- lifecycle ----------------------------------------------------------------------

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._source_error = None
        self._task = asyncio.create_task(self._run(), name=f"stage-{self.stage.id}")

    async def stop(self) -> None:
        task = self._task
        if task is None:
            return
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._task = None
        if self.state is not StageState.STOPPED:
            self._set_state(StageState.STOPPED, "stopped by operator")

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def _run(self) -> None:
        queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=QUEUE_CHUNKS)
        self.session = ManagedSttSession(
            self.stage,
            self._engine,
            emit=self._emit,
            on_state=self._on_session_state,
            rotate_seconds=float(self._settings.session_rotate_seconds),
        )
        source: AudioSource | None = None
        pump: asyncio.Task[None] | None = None
        ticker = asyncio.create_task(self._metrics_loop(), name=f"metrics-{self.stage.id}")
        try:
            try:
                source = self._source_factory(
                    self.stage.source,
                    ffmpeg_bin=self._settings.ffmpeg_bin,
                    realtime=True,
                    loop=self.stage.loop,
                )
            except Exception as exc:
                self._source_error = f"source error: {exc}"
                self._set_state(StageState.STOPPED, self._source_error)
                return
            pump = asyncio.create_task(self._pump(source, queue), name=f"pump-{self.stage.id}")
            await self.session.run(queue)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._log.exception("stage runner crashed")
            self._set_state(StageState.STOPPED, f"runner crashed: {exc}")
        finally:
            for task in (pump, ticker):
                if task is not None and not task.done():
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await task
            if source is not None:
                with contextlib.suppress(Exception):
                    await source.close()

    async def _pump(self, source: AudioSource, queue: asyncio.Queue[bytes | None]) -> None:
        try:
            async for chunk in source.chunks():
                await queue.put(chunk)
        except IngestError as exc:
            self._source_error = f"source error: {exc}"
            self._log.error("ingest failed: %s", exc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._source_error = f"source error: {exc}"
            self._log.exception("ingest crashed")
        finally:
            with contextlib.suppress(asyncio.CancelledError):
                await queue.put(None)

    # -- events -------------------------------------------------------------------------

    def _on_session_state(self, state: StageState, detail: str | None) -> None:
        if state is StageState.STOPPED and self._source_error:
            detail = self._source_error
        self._set_state(state, detail)

    def _set_state(self, state: StageState, detail: str | None) -> None:
        self.state = state
        self.detail = detail
        self._log.info("state=%s detail=%s", state.value, detail)
        self._bus.publish(
            self.stage.id, StatusEvent(stage_id=self.stage.id, state=state, detail=detail)
        )

    def _emit(self, segment: Segment) -> None:
        lang = short_code(segment.language) if segment.language else None
        lang = lang or self.stage.primary_source_lang or "und"
        self.metrics.record(segment.latency_ms, is_final=segment.is_final)
        if self._settings.log_transcripts:
            self._log.info(
                "caption seq=%s final=%s lang=%s text=%s",
                segment.seq,
                segment.is_final,
                lang,
                segment.text,
            )
        self._bus.publish(
            self.stage.id,
            CaptionEvent(
                stage_id=self.stage.id,
                seq=segment.seq,
                lang=lang,
                source_lang=lang,
                is_final=segment.is_final,
                text=segment.text,
                original=None,
                t_audio_ms=segment.t_audio_ms,
                latency_ms=segment.latency_ms,
            ),
        )

    def metrics_event(self) -> MetricsEvent:
        stats = self.session.stats if self.session else None
        return MetricsEvent(
            stage_id=self.stage.id,
            p50_ms=self.metrics.finals.p50,
            p95_ms=self.metrics.finals.p95,
            rotations=stats.rotations if stats else 0,
            errors=stats.errors if stats else 0,
        )

    async def _metrics_loop(self) -> None:
        while True:
            await asyncio.sleep(self._metrics_interval)
            self._bus.publish(self.stage.id, self.metrics_event())

    def snapshot(self) -> dict[str, Any]:
        stats = self.session.stats if self.session else None
        return {
            "id": self.stage.id,
            "name": self.stage.name,
            "state": self.state.value,
            "detail": self.detail,
            "source_lang": list(self.stage.source_lang),
            "targets": list(self.stage.targets),
            "languages": self.stage.languages(),
            "listeners": self._bus.listeners(self.stage.id),
            "dry_run": self._settings.dry_run,
            "session_id": self.session.session_id if self.session else None,
            "rotations": stats.rotations if stats else 0,
            "errors": stats.errors if stats else 0,
            "captions_final": self.metrics.captions_final,
            "p50_ms": self.metrics.finals.p50,
            "p95_ms": self.metrics.finals.p95,
            "interim_p95_ms": self.metrics.interims.p95,
        }


class StageManager:
    def __init__(
        self,
        stages: StagesFile,
        *,
        engine: SttEngine,
        bus: Bus,
        settings: Settings,
        source_factory: SourceFactory = open_source,
        metrics_interval: float = 5.0,
    ) -> None:
        self.bus = bus
        self.settings = settings
        self.runners: dict[str, StageRunner] = {
            stage.id: StageRunner(
                stage,
                engine=engine,
                bus=bus,
                settings=settings,
                source_factory=source_factory,
                metrics_interval=metrics_interval,
            )
            for stage in stages.stages
        }

    def get(self, stage_id: str) -> StageRunner | None:
        return self.runners.get(stage_id)

    async def start_all(self) -> None:
        for runner in self.runners.values():
            await runner.start()

    async def stop_all(self) -> None:
        await asyncio.gather(*(runner.stop() for runner in self.runners.values()))

    def snapshot(self) -> list[dict[str, Any]]:
        return [runner.snapshot() for runner in self.runners.values()]
