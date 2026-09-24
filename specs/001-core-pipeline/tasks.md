# Tasks 001 — core-pipeline

**Plan:** specs/001-core-pipeline/plan.md · Legend: `[P]` parallelizable · `[H]` needs human · each task ≤ 45 min.

Order is a **vertical slice first** (config → WAV source → fake engine → bus → WS → minimal Fogón → real Gemini STT → smoke) so that M1 ("a sample file flows ffmpeg → STT → WS → browser, interim + final") is reachable by 18:30Z; packaging, samples, mvp-check and docs follow before M2.

| ID | Task | Refs | Verify | Status |
|---|---|---|---|---|
| T-001-01 | Python scaffold: `pyproject.toml` (uv, deps from plan §5, `license = "Apache-2.0"`, ruff/mypy/pytest config), `.python-version` = 3.12, `lenguaraz/__init__.py`, `tests/conftest.py` with a `no_network` autouse guard; `make verify` runs the real toolchain and is green | FR-001-15, AC-14 | `make verify` | ☑ |
| T-001-02 | Failing tests then `config.py`: `Settings` (env) + `StagesFile`/`StageConfig` (YAML) with validators (unique id, non-empty source, BCP-47 shape, targets short codes, glossary ≤ 100) and a readable error on failure | FR-001-01, AC-2, AC-1 | `uv run pytest tests/test_config.py` | ☑ |
| T-001-03 | Failing tests then `models.py` (states, events, close codes) and `bus/memory.py` with bounded per-subscriber queues and drop-oldest-interim eviction | FR-001-07, AC-7 | `uv run pytest tests/test_bus.py` | ☑ |
| T-001-04 | Failing tests then `stt/base.py`, `stt/fake.py` (`ScriptedSttSession`, `FakeSttEngine` from reference text), `stt/session.py` (`ManagedSttSession`: states, seq, reconnect with backoff + jitter, `t_audio_ms`/`latency_ms`, timer reopen) | FR-001-03, FR-001-04, FR-001-06, AC-4, AC-5 | `uv run pytest tests/test_stt_session.py` | ☑ |
| T-001-05 [P] | Failing tests then `ingest/base.py`, `ingest/wav.py` (stdlib, real-time paced, 3,200-byte chunks), `ingest/ffmpeg.py` (arg builder, subprocess lifecycle, clean kill; `FFMPEG_BIN` override) | FR-001-02, AC-3 | `uv run pytest tests/test_ingest.py` | ☑ |
| T-001-06 | Failing tests then `runner.py` (`StageRunner` TaskGroup, `StageManager`) and `metrics.py` (p50/p95 window, `metrics` event every 5 s); two fake stages isolated | FR-001-05, FR-001-11, FR-001-13, AC-8, AC-14 | `uv run pytest tests/test_runner.py tests/test_metrics.py` | ☑ |
| T-001-07 | Failing tests then `api/app.py`, `api/ws.py`, `logging.py`, `cli.py serve`; `/healthz`, `/api/stages`, `WS /ws/{stage}?lang=` (status first, 4404/4400/4429, per-IP bucket, only `ping` accepted), static SPA mount; `make dev` | FR-001-08, FR-001-09, AC-1, AC-6, NFR-001-02 | `uv run pytest tests/test_api.py tests/test_ws.py` | ☐ |
| T-001-08 | Placeholder samples for the dry run until TTS runs: `samples/en_placeholder.wav` + `es_placeholder.wav` generated locally (ffmpeg tone, 30 s) with `.txt`/`.json` references; default `stages.yaml` with two stages; `ENGINE=fake make dev` streams captions on both WS | FR-001-04, FR-001-11, AC-9 | `ENGINE=fake uv run lenguaraz serve` + `uv run pytest tests/test_e2e_fake.py` | ☐ |
| T-001-09 [P] | Frontend: Vite + React + TS + Tailwind in `web/`; Home (stage list with state) and Fogón (captions, language picker, font size, contrast, dark, `aria-live`, DRY-RUN badge, reconnecting WS); vitest tests for caption merge + a11y persistence; build wired into `make verify` | FR-001-10, AC-10 | `cd web && npm test && npm run build` | ☑ |
| T-001-10 | Gemini engine `stt/gemini.py` per plan §2 (config from stage/settings, sender + receiver tasks, event mapping, `APIError` → error event); unit test with a monkeypatched `client.aio.live.connect` double; `tools/smoke_stt.py` + `make smoke-stt` (WER, interim p50/p95, end-of-utterance → final p50/p95, usage tokens → `docs/metrics.md`) | FR-001-03, AC-11 | `uv run pytest tests/test_stt_gemini.py` | ☐ |
| T-001-11 [H] | Owner confirms `GEMINI_API_KEY` in `.env` → run `make smoke-stt` on the EN sample; then **H1**: owner watches `/fogon/main` with the real engine and listens to the clip. Record numbers in `docs/metrics.md`. **= M1 exit** | AC-11, NFR-001-01, H1 | `make smoke-stt` + human verdict | ☐ |
| T-001-12 [H quota] | `tools/samples.py` (sentence-by-sentence TTS with `GEMINI_TTS_MODEL`, 800 ms gaps, ffmpeg resample to 16 kHz, `.txt` + `.json` boundaries), original EN/ES scripts dense with technical terms; `make samples`; replace placeholders; `tests/test_samples.py` (format, duration, size < 5 MB) | FR-001-12, AC-12 | `make samples && uv run pytest tests/test_samples.py` | ☐ |
| T-001-13 | `Dockerfile` (multi-stage, `python:3.12-slim` + uv + ffmpeg, non-root), `docker-compose.yml` (env, read-only mounts, healthcheck), `make up`, `make demo`, `examples/stages.minimal.yaml` | FR-001-15, FR-001-11, AC-9 | `docker compose build && make up` → `/healthz` 200 | ☐ |
| T-001-14 | `tools/mvp_check.py` + `make mvp-check`: in-process app, MVP-1/2/3/5/6/7 checks in fake mode; real mode when a key is present (MVP-4 added by 002) | AC-9, Art. I.5 | `make mvp-check` | ☐ |
| T-001-15 | Docs: README skeleton (story + naming table + 3-command quickstart + requirements + credentials/models + 18+/paid tier + license), `docs/deploy/quickstart.md` (dry run + real), `docs/configuration.md` (every env var and YAML field), `docs/architecture.md`, `docs/metrics.md` (method); `scripts/docs_check.py` + `make docs-check` | FR-001-14, AC-13 | `make docs-check` | ☐ |
| T-001-16 | Converge: re-read spec vs code, fix drift or amend spec with changelog, mark spec `Shipped`, update STATE.md and `docs/decisions.md` | Art. III.3 | `make verify && make mvp-check` | ☐ |

## Estimate vs clock
Upper-bound estimates sum to ≈ 8 h of task budget; the agent executes most tasks well under their ceiling, but the clock is the real constraint: **M1 (18:30Z)** needs T-01…T-08 + T-10 + T-11 (≈ 2h15m available at 16:15Z), and **M2 (21:00Z)** needs the rest of 001 plus feature 002. Rules for this feature:
- T-01…T-08 are executed strictly in order; T-09 runs in parallel (isolated in `web/`, fixed event contract).
- If T-08 is not green by **17:45Z**, T-09's Fogón is reduced to captions + language picker + DRY-RUN badge (a11y controls after M1) — ladder item 6 (cosmetic UI), no MVP gate touched.
- If T-11 is not done by **18:30Z**, M1 slips but M2 is protected by starting 002 no later than **19:15Z**; ladder item 5 (progressive translation) is cut preemptively if 002 starts after 19:30Z.
- T-12 (real TTS samples) needs quota and the owner's presence; placeholders keep the dry run working meanwhile.

## Definition of Done (feature)
- [ ] All tasks ☑ and all ACs pass
- [ ] `make verify` green
- [ ] Docs updated per Art. XVII.D.6 (configuration / architecture / troubleshooting / runbook as applicable)
- [ ] New files carry SPDX headers; `make license-check` green (tool lands in 007; `make spdx-check` green now)
- [ ] STATE.md updated, commit tagged if milestone
