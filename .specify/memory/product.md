# Product Brief, Target Architecture & Feature Backlog

## 1. Users
- **Audience member** (phone/laptop at the venue or remote): picks a stage and a language, reads live subtitles.
- **Production operator**: starts/stops stages, monitors health, feeds OBS overlays, exports transcripts.
- **Conference organizer / deployer**: deploys in minutes for any event, predicts cost.

## 2. Target architecture (decided; changes require spec amendment)

```
Sources (per stage)                Lenguaraz service (FastAPI, asyncio)                        Consumers
─────────────────                  ───────────────────────────────────                        ─────────
file / HLS / RTMP / SRT ─ffmpeg─▶  Ingest ─▶ StageRunner ─▶ SttSession (managed, rotating) ─▶  Bus ─▶ WS /ws/{stage}?lang=  → Audience web
browser mic / tab ──WS /ingest──▶           │               gemini-3.5-transcribe-live          │     /overlay/{stage}        → OBS browser source
                                            │                                                  │     /admin                  → Operator
                                            └─▶ TranslationFanout (per target lang) ───────────┘     /api/stages/{id}/export → SRT/VTT/TXT
                                                 text model (Flash-Lite), glossary + context
                                            └─▶ (optional) Interpreter: live-translate → audio WS
Bus: in-memory by default; Redis pub/sub when REDIS_URL is set (multi-worker).
```

Key design decisions:
- **D1** Server-side ingest with ffmpeg is the primary path (any stream a conference already has). Browser capture is secondary.
- **D2** STT with the dedicated live transcription model: `custom_vocabulary` for glossary quality, interim results for latency, auto language detection for ES↔EN.
- **D3** Translation as text fan-out: one STT per stage feeds all languages; glossary injected in the translation prompt; pass-through when source == target.
- **D4** **Progressive translation**: translate the stable prefix of the interim hypothesis (debounced) and replace when the final arrives. Feature-flagged; measured.
- **D5** Make-before-break session rotation; never depend solely on resumption.
- **D6** Single deployable container + optional Redis. Frontend built statically and served by FastAPI.
- **D7** Engine interfaces (`SttEngine`, `TranslationEngine`) allow a Gemma offline engine.
- **D8** Demand-driven language fan-out: active languages = `always_on` ∪ languages with ≥1 listener; reconcile with 250 ms debounce and 10 s grace (prior-art PA-1 L1, PA-2).
- **D9** LiveKit is an optional adapter for large-audience spoken interpretation, not the base (prior-art D9).

## 2b. Surface names (see Constitution → Naming convention)
Oído (ingest) · Lengua (STT) · Parla (translation) · Posta (rotation) · Baqueano (language demand) · Chasque (bus/fan-out) · Fogón `/fogon/{stage}` (audience) · Mangrullo `/mangrullo` (admin/monitoring) · Pizarrón `/pizarron/{stage}` (overlay) · Diccionario (glossary) · Acta (export).
APIs stay technical: `/api/...`, `WS /ws/{stage}`, `/healthz`.

## 3. Stack
Python 3.12 + uv · FastAPI + uvicorn · pydantic v2 + pydantic-settings · google-genai · ffmpeg · Vite + React + TypeScript + Tailwind · pytest + ruff + mypy · Docker Compose · optional Redis · GitHub Actions (Trivy, gitleaks, Syft).

## 4. Event contract — `WS /ws/{stage_id}?lang={code}`
```json
{"type":"caption","stage_id":"main","seq":128,"lang":"es","source_lang":"en",
 "is_final":true,"text":"...","original":"...","t_audio_ms":734200,"latency_ms":1180}
{"type":"status","stage_id":"main","state":"LIVE","detail":null}
{"type":"metrics","stage_id":"main","p50_ms":900,"p95_ms":1600,"rotations":3,"errors":0}
```
Interim: same `seq`, `is_final:false`; the client replaces the line; the final commits it.

## 5. Configuration — `stages.yaml`
```yaml
stages:
  - id: main
    name: "Main Stage"
    source: "samples/en_kubernetes.wav"   # file | http(s) HLS | rtmp:// | srt:// | device
    source_lang: ["en-US"]                # [] = auto-detect
    targets: ["es", "en"]
    talk: { title: "...", abstract: "..." }
    glossary: ["Kubernetes", "eBPF", "Nerdearla"]
```
Env: `ALWAYS_ON_LANGS=es`, `LANG_GRACE_SECONDS=10`, `LANG_RECONCILE_DEBOUNCE_MS=250`, `ENGINE=gemini|fake` (fake = credential-free dry run, clearly labeled in the UI), `GEMINI_API_KEY`, `ADMIN_TOKEN`, `GEMINI_STT_MODEL`, `GEMINI_TRANSLATE_MODEL`, `GEMINI_INTERPRETER_MODEL`, `SESSION_ROTATE_SECONDS=540`, `STT_MODE=SMART`, `PROGRESSIVE_TRANSLATION=true`, `REDIS_URL`, `LOG_TRANSCRIPTS=false`.

## 6. Feature backlog (spec one at a time, in this order)

| # | Feature | Priority | Covers | Timebox |
|---|---|---|---|---|
| 001 | **core-pipeline**: repo bootstrap (Apache-2.0 LICENSE verbatim, NOTICE, SPDX headers), config (`stages.yaml`, `branding.yaml`, env), ffmpeg ingest, managed STT (interim+final), bus, public WS, audience view (stage + language picker), ≥2 concurrent stages, generated test audios, **dry-run engine (`ENGINE=fake`)**, docs: README skeleton + quickstart + configuration | P0 / MVP | MVP-1,2,3,5,6,7 · Art. XVII | 3 h |
| 002 | **translation**: TranslationEngine, Gemini text translator with glossary + context, **demand-driven fan-out (D8)** ES/EN/PT with `always_on` targets, pass-through, progressive translation flag | P0 / MVP | MVP-4, Quality, Latency | 2 h |
| 003 | **resilience**: rotation make-before-break + GoAway, backoff, states, dedupe, per-stage isolation | P0 | Art. VI, Latency | 1.5 h |
| 004 | **operations**: admin panel (Bearer), metrics p50/p95, start/stop, glossary edit, OBS overlay, SRT/VTT/TXT export, QR per stage | P1 | Operation, extras | 2 h |
| 005 | **scale-proof**: simulator N stages, latency/cost/memory report from usage metadata, optional RedisBus + **per-stage Redis lock** so `--scale worker=N` never duplicates a stage (PA-1 L5, L7) | P1 | Scalability | 1.5 h |
| 006 | **auto-glossary**: title/abstract → prioritized terms (structured output), merged ≤100 into `custom_vocabulary` and translation glossary; before/after quality check | P1 | Quality, Innovation | 1 h |
| 007 | **hardening & CI**: Dockerfile non-root/read-only, compose healthcheck, gitleaks, Trivy, SBOM, **`make license-check` + generated THIRD_PARTY_LICENSES.md**, SPDX header check, SECURITY.md | P0 | Deployment · Art. XVII.A-B | 1 h |
| 008 | **deployability docs & submission**: complete the Art. XVII.D documentation set (deploy/quickstart, **cloud-run (PA-1 L6)**, production, scaling, audio-sources, configuration, operations runbook, customization, cost, architecture, security, privacy, troubleshooting, CONTRIBUTING, CODE_OF_CONDUCT, CHANGELOG, examples/), `make docs-check`, **`make fresh-clone-test`**, README EN + ES with **Prior art & acknowledgments**, how it was built (SDD), Devpost draft, video script, EN SRT | P0 | Deployment & Operation · Art. XVII.D | 2.5 h |
| 009 | **browser-ingest**: mic / tab audio → AudioWorklet → 16 kHz Int16 → `/ingest` | P2 | Demo, Operation | 1 h |
| 010 | **interpreter-audio**: live-translate spoken channel, one shared session per (stage, language), strictly on-demand with grace teardown, original-audio ducking option, "Listen" button (PA-1 L1, PA-4) | P2 | Innovation | 1.5 h |
| 011 | **gemma-offline**: TranslationEngine (and optionally SttEngine) over a local OpenAI-compatible server running Gemma | P3 | Innovation | 1.5 h |

Features 001–008 are the winning core. 009–011 only if the milestone clock allows (see CLAUDE.md).

**Docs-as-you-go (Art. XVII.D.6):** every feature updates the docs it affects in the same PR/commit series (new env var → `docs/configuration.md`; new endpoint → `docs/architecture.md`; new failure mode → `docs/troubleshooting.md` and the runbook). Feature 008 completes and verifies the set; it does not start it.

## 7. Event-agnostic rule
Nothing about a specific event is hardcoded. Nerdearla is one example configuration (`examples/stages.multitrack.yaml` + `examples/branding.example.yaml` referencing the official logo page, logo files git-ignored).
