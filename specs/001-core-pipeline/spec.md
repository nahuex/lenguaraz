# Spec 001 — core-pipeline

**Status:** Approved · **Owner:** human · **Author:** agent · **Created:** 2026-09-24T15:58Z
**Constitution:** v1.0.0 · **Backlog row:** product.md §6 #001

## 1. Why
Nothing else exists until audio becomes captions in a browser. This feature delivers the spine of Lenguaraz: stages described in configuration, audio pulled by ffmpeg from whatever a conference already has (file, HLS, RTMP, SRT), live transcription with interim and final segments, a fan-out bus, a public WebSocket and the audience view (Fogón), for at least two stages at once, plus bundled test audio and a credential-free dry run. It moves **Quality** (glossary-biased STT, interim + final), **Latency** (interim captions, measured per caption) and **Deployment & Operation** (one YAML, one command, dry-run mode, docs written alongside). It closes MVP gates 1, 2, 3, 5, 6 and 7; gate 4 is feature 002.

## 2. User stories
- **US-1 (P0)** As an audience member, I want to open a link on my phone, pick a stage and read live captions in the language being spoken, so that I can follow a talk from anywhere in the venue or remotely.
- **US-2 (P0)** As a production operator, I want to describe my stages in one YAML file (audio source, language hints, glossary) and start everything with one command, so that I never touch code on event day.
- **US-3 (P0)** As a deployer evaluating the project, I want to try it with the bundled test audio and without any credentials, so that I can see the whole UI before creating an API key.
- **US-4 (P1)** As an operator, I want to see each stage's state on the home page, so that I notice a broken feed before the audience does.
- **US-5 (P1)** As a contributor, I want the Gemini engine behind an interface with a fake implementation, so that tests run without quota and an open-model engine can be added later.

## 3. Functional requirements
| ID | Requirement | Traces to |
|---|---|---|
| FR-001-01 | The system MUST load `stages.yaml` (per stage: `id`, `name`, `source`, `source_lang[]`, `targets[]`, `talk{title,abstract}`, `glossary[]`) and environment settings (`ENGINE`, `GEMINI_API_KEY`, `ADMIN_TOKEN`, `GEMINI_STT_MODEL`, `GEMINI_TTS_MODEL`, `STT_MODE`, `SESSION_ROTATE_SECONDS`, `LOG_TRANSCRIPTS`, `STAGES_FILE`, `HOST`, `PORT`) through pydantic models, and MUST fail fast with a message naming the offending field on invalid config (duplicate id, missing source, bad language code). | US-2 · Art. XI.1 · Art. VIII.3 |
| FR-001-02 | **Oído (ingest):** the system MUST run one ffmpeg subprocess per stage that decodes any ffmpeg-readable source (local file, http(s)/HLS, `rtmp://`, `srt://`) into raw s16le, mono, 16 kHz, delivered downstream as 100 ms chunks (3,200 bytes); files MUST replay in real time (`-re`); the process MUST be terminated cleanly on stop or on runner cancellation, never leaving orphans. | MVP-1 · GT-3 |
| FR-001-03 | **Lengua (STT):** the system MUST define an `SttEngine` interface and a Gemini implementation that opens a Live API session with the live transcription model (`GEMINI_STT_MODEL`), `response_modalities=["TEXT"]`, `input_audio_transcription` with `language_codes` from the stage, `custom_vocabulary` from the stage glossary (capped at 100 terms) and `mode` from `STT_MODE`; it MUST emit interim and final segments as `Segment{seq, text, is_final, t_audio_ms}` with a monotonically increasing `seq` where every interim of an utterance and its final share the same `seq`. | MVP-3 · GT-2 · Art. IV |
| FR-001-04 | **Dry run:** with `ENGINE=fake` the system MUST produce interim and final captions from the bundled reference transcripts, timed to the audio replay, with no network access and no credentials; every page MUST show a visible "DRY-RUN" badge in this mode. | US-3 · Art. XVII.D.3 · Art. XII.2 |
| FR-001-05 | **Stage runner:** each stage MUST run inside its own `asyncio.TaskGroup` (ingest → STT → bus) and MUST always be in exactly one state of `IDLE | STARTING | LIVE | ROTATING | DEGRADED | STOPPED`, published as a `status` event on every transition with a human-readable `detail`; a crash, quota error or bad source in one stage MUST NOT affect any other stage. | Art. VI.3 · Art. VI.4 |
| FR-001-06 | **Session lifetime (minimum):** when the STT session ends (server `GoAway`, close, or the 10-minute limit) the runner MUST reopen a session automatically with exponential backoff + jitter and continue; captions MAY gap in this feature (zero-gap make-before-break is feature 003). | Art. VI.1–2 · GT-5 |
| FR-001-07 | **Chasque (bus):** an in-memory per-stage publish/subscribe bus with bounded per-subscriber queues; under backpressure it MUST drop the oldest *interim* events first and MUST never drop a final caption or a status event. | Art. VII.2 · PA-1 L4 |
| FR-001-08 | **Public WebSocket** `GET /ws/{stage_id}?lang={code}` MUST emit events exactly as product.md §4 (`caption`, `status`, `metrics`): a `status` event immediately on connect, then captions; in this feature `lang` MUST equal the stage's source language (translated languages arrive with 002); an unknown stage MUST close with code 4404; connections MUST be rate-limited per IP and accept no client messages other than `ping`. | MVP-5 · MVP-7 · Art. VIII.3 |
| FR-001-09 | **HTTP API:** `GET /healthz` (200 with engine mode and stage count), `GET /api/stages` (id, name, state, source_lang, targets, listener count, dry_run flag), and the built frontend served statically from the same process. | Art. XI.2 · D6 |
| FR-001-10 | **Fogón (audience view)** at `/fogon/{stage}`: captions where an interim replaces the current line and a final commits it; a language picker populated from the stage's `source_lang` + `targets` (targets become selectable with 002); font-size control, high-contrast and dark modes persisted locally; the caption region uses `aria-live="polite"`; the WebSocket reconnects with backoff. **Home** at `/` lists stages with state, speaker language and a link to each Fogón. | MVP-5 · MVP-7 · Art. X |
| FR-001-11 | The system MUST process **at least two stages concurrently** in one process, demonstrated with the two bundled samples. | MVP-6 · Art. VII.1 |
| FR-001-12 | **Test audio:** `make samples` MUST generate an English and a Spanish clip (45–90 s each, dense with technical terms and proper names, original text written for this project) using the Gemini TTS model from `GEMINI_TTS_MODEL`, as 16 kHz mono WAV in `samples/`, each with a reference transcript `.txt`; total size under 5 MB; both committed under Apache-2.0. `make demo` MUST start the two sample stages. | MVP-2 · Art. I.8 · Art. XVI · GT-13 |
| FR-001-13 | **Observability:** JSON logs carrying `stage_id`, `session_id`, `seq` and `component` (surface name); every caption event MUST carry `latency_ms` (wall-clock at publish minus the wall-clock at which the audio position `t_audio_ms` was sent to the engine); a `metrics` event per stage every 5 s with p50/p95 over the last 200 captions, `rotations` and `errors`. Transcript text MUST NOT be logged unless `LOG_TRANSCRIPTS=true`. | Art. V.1 · Art. IX.2 |
| FR-001-14 | **Docs-as-you-go:** README skeleton (Lenguaraz story, naming glossary table, 3-command quickstart, license), `docs/deploy/quickstart.md` (incl. dry run), `docs/configuration.md` (every env var and every `stages.yaml` field with type, default, example) and `docs/architecture.md` (diagram + event contract) MUST be written in this feature. `make docs-check` MUST at least verify that every settings field appears in `docs/configuration.md`. | Art. XVII.D |
| FR-001-15 | **Packaging & license:** `pyproject.toml` (`license = "Apache-2.0"`, pinned deps, ruff/mypy/pytest config), `web/package.json` (`"license": "Apache-2.0"`), `Dockerfile`, `docker-compose.yml` so that `cp .env.example .env && docker compose up` works; SPDX header on every new source file. | Art. XVII.A.4 · Art. XI.1 |

## 4. Non-functional requirements
| ID | Requirement | Measure |
|---|---|---|
| NFR-001-01 | Interim caption visible after speech | p95 ≤ 1.5 s, from `latency_ms` of interim events during `make smoke-stt`, recorded in `docs/metrics.md` with date |
| NFR-001-02 | Fan-out added latency (bus publish → WebSocket send) | p95 ≤ 150 ms, measured in-process with the fake engine by `pytest tests/test_ws.py::test_fanout_latency` |
| NFR-001-03 | Test suite | Fake-engine suite completes in < 60 s with zero network calls (`pytest --disable-socket` or equivalent guard) |
| NFR-001-04 | Audience view | Usable at 360 px width; WCAG 2.1 AA contrast in default, dark and high-contrast themes (checked in the plan with the token palette) |
| NFR-001-05 | Footprint | One process with two fake stages ≤ 200 MB RSS (recorded, not gated, in `docs/metrics.md`) |

## 5. Acceptance criteria (executable)
- **AC-1** Given a `stages.yaml` with two stages, when the service starts, then `GET /api/stages` lists both with a valid state and `GET /healthz` returns 200 — verified by `pytest tests/test_api.py`
- **AC-2** Given a `stages.yaml` with a duplicate id, a missing source or an invalid language code, when the service starts, then it exits non-zero and the message names the field — verified by `pytest tests/test_config.py`
- **AC-3** Given a 16 kHz WAV sample, when ingest runs with real-time replay, then every chunk is 3,200 bytes, chunks arrive at 10/s ± 20 % and stopping the stage terminates ffmpeg within 2 s — verified by `pytest tests/test_ingest.py` (skipped with a reason when ffmpeg is absent)
- **AC-4** Given a `FakeLiveSession` scripted with interim, interim, final for one utterance, when the runner consumes it, then the bus receives three caption events sharing one `seq` with `is_final` false, false, true — verified by `pytest tests/test_stt_session.py`
- **AC-5** Given a `FakeLiveSession` that raises a transient error and then a `GoAway`, when the runner handles them, then the stage passes through `DEGRADED`/`ROTATING` back to `LIVE` and no final segment is lost — verified by `pytest tests/test_stt_session.py::test_reconnect`
- **AC-6** Given a LIVE stage, when a client connects to `/ws/{stage}?lang=<source>`, then the first event is `status` and following events validate against the caption schema; an unknown stage closes with 4404 — verified by `pytest tests/test_ws.py`
- **AC-7** Given a subscriber with queue size N, when 3N interim events and one final are published while it is stalled, then it still receives the final and the newest interims — verified by `pytest tests/test_bus.py`
- **AC-8** Given two fake stages, when both run for 5 s and one is stopped, then both emitted captions independently and the other remains `LIVE` — verified by `pytest tests/test_runner.py::test_two_stages_isolated`
- **AC-9** Given `ENGINE=fake` and no API key, when `make dev` (or `make up`) runs and `/fogon/main` is opened, then captions appear within 5 s and a DRY-RUN badge is visible — verified by `make mvp-check` (fake mode) and by the human at H2
- **AC-10** Given the Fogón page, when font size, contrast or dark mode change, then the choice survives a reload and the caption container has `aria-live="polite"` — verified by `cd web && npm test`
- **AC-11** Given `GEMINI_API_KEY` and the EN sample, when `make smoke-stt` runs, then at least one final caption arrives, word error rate against the reference is ≤ 25 % and interim p50/p95 latency are printed — verified by `make smoke-stt` (human confirms quota) → feeds H1
- **AC-12** Given `make samples` has run, when the repo is inspected, then `samples/en_*.wav`, `samples/es_*.wav` (16 kHz mono, 45–90 s) and their `.txt` references exist and total < 5 MB — verified by `pytest tests/test_samples.py`
- **AC-13** Given the docs, when `make docs-check` runs, then every settings field is documented in `docs/configuration.md` and every relative link resolves — verified by `make docs-check`
- **AC-14** Given the repo, when `make verify` runs, then ruff, mypy, pytest, the frontend build and `spdx-check` are green — verified by `make verify`

## 6. Out of scope
- Translation, language demand and progressive translation (002).
- Zero-gap make-before-break rotation and dedupe (003); this feature only reconnects.
- Admin panel, glossary editing, overlay, export, QR (004); Redis bus and simulator (005); auto-glossary (006); CI, Trivy, SBOM, license-check (007); full deploy docs (008); browser ingest (009).
- Speaker diarization and word-level timestamps (not available on the Live API, GT-2.5).

## 7. Open questions
- [x] Q1 Default `STT_MODE`: `SMART` (cleaner captions) or `VERBATIM`? (blocking? no · default: `SMART`, per-stage override allowed) → default applied
- [x] Q2 Sample clip topics: EN "Kubernetes, eBPF and observability at a conference", ES "Python asyncio, Docker y despliegue de un servicio de subtítulos"; original scripts written by us (blocking? no · default: yes) → default applied
- [x] Q3 Language codes: explicit BCP-47 per stage when known (`en-US`, `es-419`) and `[]` for auto-detect in mixed stages (blocking? no · default: explicit in samples, auto documented) → resolved with GT-2.2
- [x] Q4 Latency definition: `latency_ms` = publish wall-clock − wall-clock at which `t_audio_ms` was sent (file replay gives an exact audio timeline; live streams use the ingest clock) (blocking? no) → resolved, recorded in FR-001-13

## Changelog
- 2026-09-24T15:58Z created; Q1–Q4 resolved with defaults per CLAUDE.md §5 (logged in HUMAN_INBOX.md); Status Approved.
