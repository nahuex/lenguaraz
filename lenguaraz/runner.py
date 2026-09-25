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
from lenguaraz.config import Settings, StageConfig, StagesFile, VadMode, short_code
from lenguaraz.export import TranscriptStore
from lenguaraz.glossary.auto import AutoGlossary, merge_glossary, talk_text
from lenguaraz.ingest import AudioSource, IngestError, open_source
from lenguaraz.ingest.base import is_local_file
from lenguaraz.metrics import StageMetrics
from lenguaraz.models import CaptionEvent, MetricsEvent, StageState, StatusEvent
from lenguaraz.pricing import estimate_stage_cost
from lenguaraz.stt.base import SttEngine
from lenguaraz.stt.session import ManagedSttSession, Segment
from lenguaraz.translate.base import TranslationEngine
from lenguaraz.translate.fanout import TranslationFanout

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
        translator: TranslationEngine | None = None,
        auto_glossary: AutoGlossary | None = None,
    ) -> None:
        self.stage = stage
        self.effective_stage = stage
        self._engine = engine
        self._translator = translator
        self._auto_glossary = auto_glossary
        self.auto_glossary_terms = 0
        self.fanout: TranslationFanout | None = None
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
        self._live_once = asyncio.Event()
        self.chunks_dropped = 0
        self.transcript = TranscriptStore()
        self._recorder: asyncio.Task[None] | None = None
        self._caption_chars = 0
        self._log = logging.LoggerAdapter(
            log, {"stage_id": stage.id, "component": "ingest/transcription"}
        )

    # -- lifecycle ----------------------------------------------------------------------

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        if self._recorder is None or self._recorder.done():
            subscription = self._bus.subscribe(self.stage.id, internal=True)
            self._recorder = asyncio.create_task(
                self._record(subscription), name=f"transcript-{self.stage.id}"
            )
        self._source_error = None
        self._live_once = asyncio.Event()
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

    async def _record(self, subscription: Any) -> None:
        """Transcript export: keep every final caption (all languages) for export."""
        try:
            async for event in subscription:
                if isinstance(event, CaptionEvent):
                    self.transcript.record(event)
        except asyncio.CancelledError:
            raise
        except Exception:
            self._log.exception("transcript recorder stopped")
        finally:
            subscription.close()

    async def close(self) -> None:
        """Stop the stage and the recorder (process shutdown)."""
        await self.stop()
        if self._recorder is not None and not self._recorder.done():
            self._recorder.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._recorder

    async def _apply_auto_glossary(self) -> None:
        """Auto-glossary: prime the glossary from the talk metadata (spec 006)."""
        if self._auto_glossary is None or not self._settings.auto_glossary:
            return
        if not talk_text(self.stage):
            return
        try:
            terms = await asyncio.wait_for(self._auto_glossary.suggest(self.stage), 10.0)
        except TimeoutError:
            self._log.warning("auto-glossary timed out; using the manual glossary")
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._log.warning("auto-glossary failed: %s", exc)
            return
        merged = merge_glossary(self.stage.glossary, terms)
        self.auto_glossary_terms = len(merged) - len(self.stage.glossary)
        self.effective_stage = self.stage.model_copy(update={"glossary": merged})
        self._log.info(
            "auto-glossary added %d terms (total %d)", self.auto_glossary_terms, len(merged)
        )

    async def _run(self) -> None:
        queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=QUEUE_CHUNKS)
        await self._apply_auto_glossary()
        self.session = ManagedSttSession(
            self.effective_stage,
            self._engine,
            emit=self._emit,
            on_state=self._on_session_state,
            rotate_seconds=float(self._settings.session_rotate_seconds),
            stall_seconds=float(self._settings.stt_stall_seconds),
            final_timeout=float(self._settings.stt_final_timeout_seconds),
            max_reconnects=self._settings.stt_max_reconnects,
            vad_silence_ms=(
                self._settings.vad_silence_ms if self._settings.vad_mode is VadMode.HYBRID else None
            ),
            vad_threshold=self._settings.vad_threshold,
            drain_seconds=self._settings.rotation_drain_seconds,
            dedupe_window=self._settings.dedupe_window_seconds,
            swap_max_wait=self._settings.rotation_swap_max_wait_seconds,
        )
        if self._translator is not None and self.stage.targets:
            self.fanout = TranslationFanout(
                self.effective_stage,
                self._translator,
                self._bus,
                self._settings,
                on_status=self._on_translation_status,
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
            if self.fanout is not None:
                with contextlib.suppress(Exception):
                    await self.fanout.stop()

    async def _pump(self, source: AudioSource, queue: asyncio.Queue[bytes | None]) -> None:
        """Feed the queue. Files wait for the first LIVE (no backlog burst); streams never
        block: when the queue is full the oldest chunk is dropped and counted."""
        local_file = is_local_file(self.stage.source)
        try:
            if local_file:
                await self._live_once.wait()
            async for chunk in source.chunks():
                if local_file:
                    await queue.put(chunk)
                    continue
                if queue.full():
                    with contextlib.suppress(asyncio.QueueEmpty):
                        queue.get_nowait()
                        self.chunks_dropped += 1
                queue.put_nowait(chunk)
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

    def _on_translation_status(self, detail: str) -> None:
        """Translation trouble is reported on the current state; STT keeps flowing."""
        self._set_state(self.state, detail)

    def _on_session_state(self, state: StageState, detail: str | None) -> None:
        if state is StageState.STOPPED and self._source_error:
            detail = self._source_error
        self._set_state(state, detail)

    def _set_state(self, state: StageState, detail: str | None) -> None:
        self.state = state
        self.detail = detail
        if state is StageState.LIVE:
            self._live_once.set()
        elif state is StageState.STOPPED:
            self._live_once.set()  # release a waiting file pump so it can exit
        self._log.info("state=%s detail=%s", state.value, detail)
        self._bus.publish(
            self.stage.id, StatusEvent(stage_id=self.stage.id, state=state, detail=detail)
        )

    def _emit(self, segment: Segment) -> None:
        lang = short_code(segment.language) if segment.language else None
        lang = lang or self.stage.primary_source_lang or "und"
        self.metrics.record(segment.latency_ms, is_final=segment.is_final)
        if segment.is_final:
            self._caption_chars += len(segment.text)
        if self._settings.log_transcripts:
            self._log.info(
                "caption seq=%s final=%s lang=%s text=%s",
                segment.seq,
                segment.is_final,
                lang,
                segment.text,
            )
        event = CaptionEvent(
            stage_id=self.stage.id,
            seq=segment.seq,
            lang=lang,
            source_lang=lang,
            is_final=segment.is_final,
            text=segment.text,
            original=None,
            t_audio_ms=segment.t_audio_ms,
            latency_ms=segment.latency_ms,
        )
        self._bus.publish(self.stage.id, event)
        if self.fanout is not None:
            self.fanout.on_caption(event)

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
        audio_seconds = (stats.bytes_sent / 32_000) if stats else 0.0
        translation_usage = self.fanout.usage() if self.fanout else {}
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
            "duplicates_dropped": stats.duplicates_dropped if stats else 0,
            "stalls": stats.stalls if stats else 0,
            "promoted_finals": stats.promoted_finals if stats else 0,
            "last_rotation_gap_ms": stats.last_rotation_gap_ms if stats else None,
            "chunks_dropped": self.chunks_dropped,
            "captions_final": self.metrics.captions_final,
            "p50_ms": self.metrics.finals.p50,
            "p95_ms": self.metrics.finals.p95,
            "interim_p95_ms": self.metrics.interims.p95,
            "active_languages": self.fanout.active_languages() if self.fanout else [],
            "translation_tokens": translation_usage,
            "translation_rate_limited": self.fanout.rate_limited() if self.fanout else 0,
            "translation_untranslated": self.fanout.untranslated() if self.fanout else 0,
            "translation_hedged": self.fanout.hedged() if self.fanout else 0,
            "running": self.running,
            "audio_seconds": round(audio_seconds, 1),
            "est_cost_usd": round(
                estimate_stage_cost(
                    audio_seconds,
                    stt_response_tokens=stats.response_tokens if stats else 0,
                    stt_response_chars=self._caption_chars,
                    translation_usage=translation_usage,
                ),
                4,
            ),
            "transcript_entries": self.transcript.counts(),
            "glossary_terms": len(self.effective_stage.glossary),
            "auto_glossary_terms": self.auto_glossary_terms,
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
        translator: TranslationEngine | None = None,
        auto_glossary: AutoGlossary | None = None,
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
                translator=translator,
                auto_glossary=auto_glossary,
            )
            for stage in stages.stages
        }

    def get(self, stage_id: str) -> StageRunner | None:
        return self.runners.get(stage_id)

    async def start_all(self) -> None:
        for runner in self.runners.values():
            await runner.start()

    async def stop_all(self) -> None:
        await asyncio.gather(*(runner.close() for runner in self.runners.values()))

    def snapshot(self) -> list[dict[str, Any]]:
        return [runner.snapshot() for runner in self.runners.values()]
