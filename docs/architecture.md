# Architecture

Lenguaraz is a single asyncio service (FastAPI) that runs one independent pipeline per
stage and fans captions out to browsers over WebSockets. Surface names come from the
lenguaraz's world; modules keep technical names.

```
stages.yaml + .env ──▶ config (pydantic)
                             │
                      StageManager ── one StageRunner per stage, each in its own TaskGroup
                             │
  file / HLS / RTMP / SRT ──▶ Oído   ingest/  (stdlib WAV reader or ffmpeg subprocess) ─▶ 3,200-byte PCM chunks
                             │
                            Lengua  stt/     ManagedSttSession ─▶ Gemini Live API (gemini-3.5-transcribe-live)
                             │               interim + final segments, seq, latency, reconnect, rotation (Posta)
                             │
                            Parla   translate/  one ordered translation worker per active language (Baqueano decides which)
                             │
                            Chasque bus/     in-memory pub/sub, bounded queues, drop-oldest-interim
                             │
                     api/ws.py  WS /ws/{stage}?lang=   ─▶  Fogón /fogon/{stage}  (audience)
                     api/app.py GET /healthz · /api/stages · /api/branding · static SPA (web/dist)
```

## Components

| Surface name | Module | Responsibility |
|---|---|---|
| Oído | `lenguaraz/ingest/` | Turn any source into raw s16le mono 16 kHz audio in 100 ms chunks. Files replay in real time; streams pass through. One ffmpeg process per stage, terminated on stop. |
| Lengua | `lenguaraz/stt/` | `SttEngine` interface; `GeminiSttEngine` (Live API) and `FakeSttEngine` (dry run). `ManagedSttSession` owns states, `seq`, latency, backoff and session rotation. |
| Posta | `lenguaraz/stt/session.py` | Make-before-break rotation: on the timer (`SESSION_ROTATE_SECONDS`) or the server's `GoAway`, the next Live session is opened while the current one keeps listening; the audio feed switches once it is connected **and at the next pause** detected by the hybrid VAD (bounded by `ROTATION_SWAP_MAX_WAIT_SECONDS`), so no sentence is split; the old session gets `audio_stream_end`, drains for `ROTATION_DRAIN_SECONDS` and is closed; late duplicates are dropped (`DEDUPE_WINDOW_SECONDS`); `seq` continues; the caption gap is measured (`last_rotation_gap_ms`). |
| Chasque | `lenguaraz/bus/` | Publish/subscribe per stage with a bounded queue per listener. Under backpressure the oldest interim is dropped first; a final or status event is never dropped (a listener that cannot keep up is closed and reconnects). |
| — | `lenguaraz/runner.py` | `StageRunner` (ingest → session → bus, metrics ticker) and `StageManager`. A failure in one stage never affects another. |
| — | `lenguaraz/api/` | FastAPI app: health, stage list, caption WebSocket with per-IP limits, SPA serving. |
| Fogón | `web/src/pages/Fogon.tsx` | Audience view: stage + language, font size, contrast, dark mode, `aria-live` captions, reconnecting socket. |
| Parla | `lenguaraz/translate/fanout.py` | One ordered worker per (stage, language): every final caption is translated with the stage glossary and the last segments as context (Interactions API, `thinking_level: minimal`); retries with backoff; on persistent failure the caption is published with `degraded: true` and the original text. Progressive translation publishes a provisional line from a debounced partial. |
| Baqueano | `lenguaraz/translate/demand.py` | Active languages = `ALWAYS_ON_LANGS` plus languages with a listener in the last `LANG_GRACE_SECONDS`, restricted to the stage's `targets`; evaluated at every caption. |
| Acta | `lenguaraz/export.py` | Bounded in-memory transcript per stage and language (start = first partial, end = final, on the audio timeline), fed from the bus; `GET /api/admin/stages/{id}/export?format=srt\|vtt\|txt&lang=` renders it. Nothing touches disk until an operator exports. |
| Mangrullo | `lenguaraz/api/admin.py`, `web/src/pages/Mangrullo.tsx` | Operator API and page behind `ADMIN_TOKEN` (Bearer, constant-time compare): stage snapshots with latency, rotations, errors, duplicates, dropped chunks, token usage and estimated cost; start/stop; exports. |
| Pizarrón | `web/src/pages/Pizarron.tsx` | Transparent overlay for OBS/vMix browser sources: `/pizarron/{stage}?lang=&lines=2&size=l&align=bottom&bg=band`. |
| Diccionario | feature 006 | Auto-glossary from talk title and abstract. |

## Stage states

Every stage is always in exactly one state: `IDLE → STARTING → LIVE ⇄ ROTATING | DEGRADED → STOPPED`.
`ROTATING` lasts from the moment the next session is being opened until the audio feed has switched (usually well under a second); captions keep flowing from the old session meanwhile.
Transitions are published as `status` events with a human-readable `detail` (for example
`connect failed: …; retry 2/5 in 1.3s`, `server GoAway (12s left)`, `source ended`).

## Event contract — `WS /ws/{stage_id}?lang={code}`

The first message is always a `status` event. Then, one JSON object per message:

```json
{"type":"caption","stage_id":"main","seq":128,"lang":"es","source_lang":"en",
 "is_final":true,"text":"...","original":"...","t_audio_ms":734200,"latency_ms":180,"degraded":false}
{"type":"status","stage_id":"main","state":"LIVE","detail":null}
{"type":"metrics","stage_id":"main","p50_ms":150,"p95_ms":420,"rotations":3,"errors":0}
```

- An **interim** caption (`is_final: false`) replaces the current line; the **final** with the
  same `seq` commits it. Every partial of an utterance shares the `seq` of its final.
- `t_audio_ms` is the audio-timeline position of the newest chunk sent to the engine.
- `latency_ms`: for an interim, milliseconds since the previous partial update of the same
  utterance; for a final, the commit delay between the last partial and the committed line.
  Speech-to-caption latency is measured with known sentence boundaries by `make smoke-stt`
  (see `docs/metrics.md`).
- `lang` is a short code (`en`, `es`, `pt`). The client may send the text `ping`; nothing
  else is accepted. Close codes: `4404` unknown stage, `4400` unsupported language,
  `4429` too many connections from one IP, `4413` listener too slow.

## HTTP endpoints

| Endpoint | Purpose |
|---|---|
| `GET /healthz` | `{"status":"ok","engine":"gemini|fake","stages":N,"version":"…"}` |
| `GET /api/stages` | One row per stage: `id`, `name`, `state`, `detail`, `source_lang`, `targets`, `languages`, `listeners`, `dry_run`, `session_id`, `rotations`, `errors`, `captions_final`, `p50_ms`, `p95_ms`, `interim_p95_ms` |
| `GET /` , `/fogon/{stage}`, `/pizarron/{stage}`, `/mangrullo` | The single-page app: home, audience view, overlay, operations |
| `GET /api/branding` | Event identity from `branding.yaml` (`event_name`, `tagline`, `primary_color`, `logo_url`, `footer`), defaults when the file is absent; `/branding/*` serves `branding/local/` read-only |
| `GET /api/admin/stages` (Bearer) | Snapshots plus `running`, `audio_seconds`, `est_cost_usd`, `transcript_entries` |
| `POST /api/admin/stages/{id}/start` · `/stop` (Bearer) | Start or stop a stage runner |
| `GET /api/admin/stages/{id}/export?format=srt\|vtt\|txt&lang=` (Bearer) | Transcript download (`Content-Disposition: attachment`) |

## Deployment shape

One container (`Dockerfile`: Node build stage → `python:3.12-slim` with uv and ffmpeg,
non-root) plus `docker-compose.yml` with a read-only filesystem. Optional Redis and multiple
workers arrive with feature 005; see `docs/deploy/` (feature 008) for production and scaling.
