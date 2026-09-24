# Prior Art — Patterns to Adopt, Gaps to Beat

> Researched 2026-09-22. **Rule (Constitution Art. I.2):** prior art is studied for *patterns and lessons*, never copied, forked or vendored. Lenguaraz is written from scratch inside the build window. The README includes a "Prior art & acknowledgments" section crediting these projects.

## PA-1 `google-gemini/gemini-live-translate-livekit` (Google, Apache-2.0)
**What it is:** Google's own broadcast translation app. An organizer speaks into a mic in a LiveKit room; attendees pick a language and hear a live AI translation; each language gets exactly one Gemini Live session shared by all its listeners. Next.js + `@livekit/rtc-node` + `gemini-3.5-live-translate-preview` with `translationConfig`. Deploy target: Cloud Run. Ships `CLAUDE.md`/`AGENTS.md`.

**Field lessons published by Google (from live events with 1k+ users, 20+ languages) — adopt:**
| # | Lesson | How Lenguaraz applies it |
|---|---|---|
| L1 | **One model session per language, shared** by all listeners; created on first request, torn down when idle | One STT per stage; translation and interpreter sessions are demand-driven and shared per (stage, language) — see D8 |
| L2 | **Free tier caps concurrent Live WebSockets (~3–5)**; paid tier (Tier 1–3) is required for multi-language events | Paid tier is a documented prerequisite for >2 concurrent stages; admin shows a clear error on 429/connection refusals |
| L3 | Captions delivered on a **reliable channel separate from audio** | Captions over WebSocket events, independent of any audio channel |
| L4 | **Serialize audio frame writes** to avoid pile-up | Bounded async queues with backpressure; drop oldest interim, never finals |
| L5 | In-memory singleton ⇒ **locked to one instance**; scaling out needs coordination (e.g., Redis) | Optional RedisBus + per-stage lock so N workers never duplicate a stage |
| L6 | Cloud Run needs `--timeout 3600`, `--no-cpu-throttling`, high `--concurrency`, secrets from Secret Manager, keep-alive traffic during events | `docs/deploy/cloud-run.md` as an alternative target; `/healthz` + admin polling keep instances warm |
| L7 | Size memory/CPU per active language (~20–30 MiB and ~10% vCPU per WebRTC bridge in their stack) | Simulator measures our own per-stage/per-language footprint and publishes a sizing table |
| L8 | **3-tier design for scale**: ingestion → per-language workers → delivery; CDN/HLS for 10k+ viewers | `docs/deploy/scaling.md` maps the same tiers: ingest workers → STT/translation workers → stateless WS delivery nodes (behind a load balancer) |
| L9 | Simple password for broadcasters; IAP for full lockdown | `ADMIN_TOKEN` for operator/ingest; docs mention IAP/reverse-proxy auth for private deployments |
| L10 | QR code per session; broadcast vs watch pages | QR per stage on Home; Admin vs Audience pages |

**Gaps Lenguaraz closes (our differentiation):**
| Their design | Lenguaraz |
|---|---|
| Ingest = organizer's browser microphone | Ingest = the stage stream a conference already has (SRT/RTMP/HLS/file via ffmpeg), plus mic/tab as secondary |
| One broadcast | N stages in parallel, managed from one admin |
| Speech-to-speech only; model accepts no instructions ⇒ no glossary | Captions-first: dedicated transcription model with `custom_vocabulary` + glossary-aware text translation; spoken interpreter as optional channel |
| ~USD 2.21 per hour **per language** (live translate pricing) | ~USD 0.54 per stage-hour for STT + cents per language for text translation (GT-6) |
| Requires a LiveKit server (WebRTC, UDP ports) | `docker compose up`; no media server needed for captions |
| No transcript export, overlay or latency metrics | SRT/VTT/TXT export, OBS overlay, p50/p95 latency, rotation and error metrics |
| Single instance | Horizontal via Redis lock per stage |
| Session lifetime handling not documented | Explicit, tested make-before-break rotation (Art. VI) |

## PA-2 `livekit-examples/gemini-live-translate` (LiveKit, MIT)
Peer video calls where each participant picks a language; a Python LiveKit Agents worker translates each speaker into every other language present, on demand.

**Adopt (patterns):**
- **Demand-set reconciliation loop:** desired sessions are computed from who is listening in which language; skip pairs where source == target; **debounce (~250 ms)** reconciliation and keep a **grace period (~10 s)** before tearing down. Their router has unit tests for the demand-set computation → we test ours the same way.
- Captions as a text stream **tagged with target language**, parallel to translated audio.
- Configuration table documenting caps and timeouts (TTL, empty-room timeout, grace, debounce, model id) → mirrored in `docs/configuration.md`.
- Audio I/O: 16 kHz mono in, 24 kHz mono out for interpreter audio.

**Not applicable:** peer-to-peer call model, LiveKit Cloud dependency.

## PA-3 `livekit-examples/live-translated-captioning` (LiveKit)
Host → listeners; each listener sets a language and receives captions; pipeline STT → LLM prompt translation → captions forwarder. Known limits: one host, UI glitches with multiple windows.

**Takeaway:** validates the captions-first "STT once, translate text per language" pipeline — the same shape as Lenguaraz — using third-party STT. Lenguaraz uses Gemini end-to-end and adds multi-stage, glossary and operations.

## PA-4 `google-gemini/gemini-live-api-examples` (Google)
- **Gen AI SDK Python example** — canonical Live session loop (reference for our `SttSession`).
- **Ephemeral tokens + raw WebSocket example** — reference pattern for feature 009 (browser ingest) if the browser ever talks to Google directly.
- **`command-line/python/translate.py`** — streams a *remote audio URL* into Live Translate, prints source/target transcripts with language codes, and plays the original softly under the translation (`--original-volume`, default 0.08). Adopt: **original-audio ducking** in the interpreter player (010); a Google-hosted sample WAV exists for smoke tests — reference it by URL in `make smoke`, never commit it.

## D8 — Demand-driven language fan-out (new design decision)
Per stage, the set of active target languages = `always_on` (from `stages.yaml`, e.g. `es` so SRT exists for every talk) ∪ languages with ≥1 connected listener. Reconcile with 250 ms debounce and 10 s grace. Interpreter audio sessions (010) are strictly on-demand. Metric: `active_languages{stage}`.

## D9 — LiveKit is optional, not the base
Captions are text; WebSocket fan-out behind any load balancer is simpler to deploy for an unknown conference than a WebRTC media server. LiveKit stays an **optional adapter** for the spoken interpreter channel at very large audiences (documented in `scaling.md`), following PA-1's 3-tier pattern.
