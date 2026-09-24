# Lenguaraz Constitution

**Version:** 1.0.1 · **Ratified:** 2026-09-24 (at kickoff, by the human owner) · **Scope:** every spec, plan, task, commit and document in this repository.

This constitution is the highest authority in the repo. When a spec, plan, task, prompt or instruction conflicts with it, the constitution wins. Articles marked **[NN]** are non-negotiable: they cannot be traded for speed, scope or convenience. Amendments follow Article XVIII.

---

## Mission

Build **Lenguaraz**: the best open source, self-hostable, real-time transcription and translation system for multi-track conferences. It takes live audio from many stages in parallel and delivers subtitles in the original language and in Spanish (plus English and Portuguese when possible), to an audience web view, to production overlays, and to exportable files. It is built on Google's Gemini audio capabilities, with an open-model path via Gemma.

Built for the Nerdearla Vibeathon 2026. Judged on: **Quality, Latency, Scalability, Deployment & Operation, Innovation.**

### Identity
**Lenguaraz** — *the open-source interpreter for every stage.*
On the 18th–19th century Río de la Plata frontier, the *lenguaraz* was the interpreter who stood between peoples who did not share a language, so that everyone in a parley could follow what was said. That is exactly this system's job: someone speaks on a stage, and every person understands it in their own language. The name and its story appear in the README (EN and ES) and in the demo video. Pronunciation note for the README: *len-gwa-RAHS*.

### Naming convention (applies to the whole repo)
Components carry **standard English names used by live-captioning platforms** on every surface — UI labels and page titles, routes, CLI subcommands, Docker service labels, metric/log component fields, docs headings — so that an operator, an audience member or a judge understands each one without explanation. The only Rioplatense word in the product is the product name **Lenguaraz** (owner decision N1, 2026-09-24T22:45Z); its story stays in one paragraph of the README and no component carries an etymology. **Inside the code**, modules keep descriptive technical names so any contributor understands them instantly. The README includes this table as its "Components" section.

| Surface name | Component | Code module | Meaning |
|---|---|---|---|
| **Ingest** (`ingest`) | Audio ingest (ffmpeg / browser) | `ingest/` | ffmpeg or WAV reader → 16 kHz mono PCM chunks |
| **Transcription** (`transcription`) | Live transcription | `stt/` | Gemini Live API session: partial and final captions, hybrid VAD, stall watchdog |
| **Translation** (`translation`) | Text translation fan-out | `translate/` | Per-language workers, glossary-aware prompts, pass-through when source == target |
| **Session rotation** (`session_rotation`) | Make-before-break session rotation | `stt/session.py` | Opens the next Live session before the current one expires; zero lost finals |
| **Language demand** (`language_demand`) | Language-demand reconciler (D8) | `translate/demand.py` | Translates only into languages with listeners (plus `always_on`) |
| **Event bus** (`event_bus`) | Event bus and audience fan-out | `bus/` | Bounded fan-out to WebSocket clients; interims may be dropped, finals never |
| **Live captions** (`/live/{stage}`) | Audience view | `web/src/pages/LiveCaptions.tsx` | Stage, language, font size, contrast, dark mode |
| **Admin** (`/admin`) | Operator dashboard | `web/src/pages/Admin.tsx`, `api/admin.py` | States, latency, cost, start/stop, exports; behind `ADMIN_TOKEN` |
| **Overlay** (`/overlay/{stage}`) | OBS/vMix overlay | `web/src/pages/Overlay.tsx` | Transparent browser source for OBS/vMix (`?lang=&lines=`) |
| **Glossary** (`glossary`) | Glossary + auto-glossary | `glossary/` | Manual list + auto-glossary from the talk title/abstract (structured output) |
| **Transcript export** (`export`) | SRT/VTT/TXT export | `export.py` | In-memory transcript per stage/language, exported as SRT/VTT/TXT |

Rules: routes and identifiers are ASCII lowercase (`live`, `overlay`, `admin`); the WebSocket path `/ws/{stage}` and every `/api/*` path are unchanged. The home page lists stages and links each one's live captions page ("Open live captions"), overlay ("Overlay for OBS") and QR. Metrics use the prefix `lenguaraz_`; metric and log `component` fields carry the lowercase identifier from the table (`ingest`, `transcription`, `translation`, `session_rotation`, `language_demand`, `event_bus`, `glossary`, `export`). Page titles follow `Live captions · <stage name> · Lenguaraz`, `Overlay · <stage name>` and `Admin · Lenguaraz`; the Admin page heading is "Admin" with the subtitle "Operator dashboard"; the live captions page heading is the stage name. Spanish copy lives only in `README.es.md` and `docs/es/`.

---

## Article I — Hackathon Compliance [NN]

1. **Build window.** All project code, specs, commits and assets are created between **2026-09-24T15:00:00Z** and **2026-09-25T15:00:00Z**. Before starting any work session, run `date -u`. If the time is before the window opens, do not create or modify project files. Git history is the evidence: commit early, commit often.
2. **Originality.** Existing libraries, models and services (Gemini, Gemma, ffmpeg, FastAPI, React…) are allowed. The solution itself is original. Never copy, fork or vendor an existing subtitle/transcription/translation project as the base — including Google's and LiveKit's examples. Prior art (`.specify/memory/prior-art.md`) is studied for **patterns and lessons only**; no code is copied from it. The README has a "Prior art & acknowledgments" section crediting the projects whose ideas informed the design.
3. **License.** The repository is under an **OSI-approved license (Apache-2.0)** from the very first commit, and clear documentation lets **any conference** deploy it. Both obligations are detailed and enforced by **Article XVII**. Nerdearla may use, adapt, fork and deploy the solution under this license.
4. **Public repository** on GitHub, with a README that explains how to run the project and which credentials and models it needs.
5. **MVP gates.** The submission is invalid unless ALL of these work and are demonstrable:
   - MVP-1: receives live audio from at least one source (microphone, audio file or stream);
   - MVP-2: test audio files are included in the repo, with a one-command way to try them;
   - MVP-3: real-time transcription of the original language (Spanish or English);
   - MVP-4: real-time translation English → Spanish;
   - MVP-5: subtitles displayed (web);
   - MVP-6: at least **two sessions processed simultaneously**, with a README section on how to scale to more;
   - MVP-7: audience view where each person chooses session and language.
6. **Demo video.** 1–2 minutes, on YouTube, using real audio from a past Nerdearla talk, explaining what it does and how to use it. English subtitles for the video are produced **with Lenguaraz itself** (SRT export).
7. **Deadline.** Devpost submission before **2026-09-25T15:00:00Z**. Internal target: **13:00Z**. Code freeze: **13:00Z** (after that, only docs/Devpost text).
8. **Media rights.** Never commit audio or video downloaded from YouTube or any third party. Repo test audio is generated (Gemini TTS) or recorded by the owner, and released under the repo license.
9. **Conduct.** Participation follows the Nerdearla code of conduct. Brand assets only from the official logo page.

## Article II — Google Platform Terms [NN]

1. The Gemini API key lives **only** on the server (environment variable). It never reaches a browser, a log line, a commit, a test fixture or a chat message.
2. Any browser-to-Google connection uses **ephemeral tokens** (single use, short expiry, `live_connect_constraints` locking model and config).
3. The README states: the service requires operators aged 18+, and deployments must not be directed at users under 18 (Gemini API Additional Terms).
4. The README recommends a **paid-tier** project for real events: on unpaid quota, Google may use content to improve products and humans may review it; on paid tier it does not. Speaker audio is third-party content.
5. Never attempt to bypass Gemini safety filters. Never use outputs to train competing models. Comply with the Prohibited Use Policy.

## Article III — Spec-Driven Development [NN]

1. **No code without a spec.** Every feature follows: `spec.md` (what & why) → `plan.md` (how, constitution check) → `tasks.md` (ordered, testable tasks) → implementation loop.
2. **Traceability.** Requirements have IDs (`FR-xxx`, `NFR-xxx`), tasks have IDs (`T-xxx`) that reference requirements, commits reference tasks (`feat(stt): rotate sessions on GoAway [T-012]`).
3. **Specs are the source of truth.** If implementation reveals the spec is wrong, stop, amend the spec (with a changelog line), then continue. Never let code and spec silently diverge.
4. **Acceptance criteria are executable** where possible (tests or scripted smoke checks), and written as Given/When/Then.
5. SDD is proportionate: small fixes use a task line in the current feature, not a new spec. No process theater.

## Article IV — Gemini-First, Docs-Verified [NN]

1. Use the official **Google Gen AI SDK** (`google-genai` for Python, `@google/genai` for TypeScript) and the patterns prescribed by the installed `gemini-api-dev` and `gemini-live-api-dev` skills.
2. **Never invent API fields, model IDs or parameters.** Before using any Gemini API surface, verify it through the Gemini Docs MCP (`search_documentation`) or the official docs, and record the doc URL in the feature `plan.md` under "Verified references".
3. Model IDs are configuration (`GEMINI_STT_MODEL`, `GEMINI_TRANSLATE_MODEL`, `GEMINI_INTERPRETER_MODEL`), never hardcoded in logic.
4. `.specify/memory/ground-truth.md` holds verified facts. It is re-verified at kickoff; any drift is corrected there first.
5. Use each model for what it is designed for: dedicated live transcription model for STT, cost-efficient text model for translation, live translate model only for spoken interpretation.

## Article V — Real-Time Performance Budgets

Targets (goals to measure against, not claims):

| Metric | Target |
|---|---|
| Original-language interim caption visible after speech | p95 ≤ 1.5 s |
| Translated caption visible after end of utterance | p95 ≤ 3.0 s |
| Audience fan-out added latency (server → browser) | p95 ≤ 150 ms |
| Session rotation caption gap | ≤ 1 s, zero lost final segments |

1. Every caption event carries `latency_ms`. Metrics expose p50/p95 per stage.
2. No latency number appears in the README, video or Devpost unless it was **measured** by the project's own tooling, with the method described.

## Article VI — Resilience [NN]

1. Live sessions have a finite lifetime (~10 min). The system **rotates sessions** make-before-break on a timer and on `GoAway`, without losing final segments.
2. Transient failures retry with exponential backoff + jitter. Permanent failures surface as stage state `DEGRADED` or `STOPPED` with a reason.
3. **No silent failure.** Every stage is always in exactly one visible state: `IDLE | STARTING | LIVE | ROTATING | DEGRADED | STOPPED`.
4. One stage failing never affects another stage.

## Article VII — Scalability & Cost

1. **One transcription stream per stage**, fanned out to N target languages as text. Cost grows with stages, not stages × languages.
2. Stage runners are independent and stateless beyond their in-memory rolling buffer; horizontal scale is by adding workers (optional Redis bus).
3. Cost per stage-hour is **computed from measured token usage** and published in the README with the pricing date.
4. Scale is **demonstrated**, not asserted: a simulator replays N stages concurrently and produces a report.

## Article VIII — Security by Default [NN]

1. Secrets: `.env` git-ignored; `.env.example` with placeholders only; gitleaks in pre-commit and CI.
2. Admin and ingest endpoints require `ADMIN_TOKEN` (Bearer). Audience endpoints are read-only.
3. All external input is validated (pydantic), size-limited, and rate-limited per IP on public WebSockets.
4. Glossary and talk metadata are **untrusted data** when placed in prompts: delimited, length-capped, never interpreted as instructions.
5. Containers: slim base, non-root user, read-only filesystem with tmpfs, healthcheck, pinned dependency versions.
6. CI runs lint, tests, Trivy (image + fs) and SBOM generation. `SECURITY.md` documents reporting.

## Article IX — Privacy

1. Audio is never persisted. Transcripts live in a bounded in-memory buffer per stage and are written to disk only on explicit export.
2. Logs never contain API keys or full transcript text by default (`LOG_TRANSCRIPTS=false`).

## Article X — Accessibility

1. Audience view meets WCAG 2.1 AA contrast, supports font-size control, high-contrast and dark modes, keyboard navigation, and an `aria-live="polite"` caption region.
2. Works on a mid-range phone browser over conference Wi-Fi (reconnects automatically).

## Article XI — Operability

1. **One command to run:** `cp .env.example .env && docker compose up`. Stages are configuration (`stages.yaml`), not code.
2. `/healthz`, structured JSON logs, admin dashboard with state, latency, rotations and errors per stage.
3. A production operator with no context can start, stop and monitor stages from the admin panel.

## Article XII — Test Discipline [NN]

1. `make verify` = lint (ruff) + types (mypy, pragmatic) + tests (pytest) + frontend build. It must be green before every commit.
2. Tests never consume real API quota: Gemini is faked (`FakeLiveSession`, `FakeTranslator`). Real-API checks live in `make smoke` and run on demand.
3. Every bug fix starts with a failing test that reproduces it.

## Article XIII — Simplicity & Scope Discipline

1. Smallest thing that satisfies the spec. No speculative abstractions except the explicit engine interfaces (`SttEngine`, `TranslationEngine`).
2. Timeboxes are real. When behind schedule, apply the scope-cut ladder in `CLAUDE.md`; never cut an [NN] article or an MVP gate.
3. Dependencies are justified in the plan; prefer the standard library.

## Article XIV — Honest Claims

README, Devpost text and video only state what the system does today. Known limitations are documented (session lifetime handling, no diarization in live mode, utterance-level timestamps, preview-model quotas).

## Article XV — Human in the Loop [NN]

1. The human owner provides secrets, accounts, taste decisions and final approvals. The agent never guesses these.
2. The agent asks through the protocol in `CLAUDE.md` (blocking vs non-blocking, batched, with a recommended default).
3. The agent never asks the human to paste a secret into chat. Secrets go into `.env` by the human.
4. Mandatory human checkpoints: kickoff inputs, first real transcription listened to, MVP demo, scale report review, quickstart read-through as an outsider, video recording, Devpost submission.

## Article XVI — Git Hygiene

Conventional Commits with task IDs; small commits; `main` always runnable; tags at milestones (`v0.1.0` MVP, `v0.2.0` scale, `v1.0.0` submission); never force-push `main`; never commit generated secrets, large binaries (>5 MB) or third-party media.

## Article XVII — Open Source License & Deployable by Any Conference [NN]

The challenge requires the solution to be under an OSI-approved license **and** to have clear documentation so that **any conference** can deploy it. This article makes both verifiable.

### A. License (OSI-approved, verified)
1. **License: Apache License 2.0**, SPDX `Apache-2.0`, listed as OSI Approved at opensource.org/licenses (GT-11). Chosen because it is permissive (any conference, commercial or community, can deploy and fork), includes an explicit patent grant, and matches Google's open model and sample-code licensing.
2. `LICENSE` contains the **verbatim official text** downloaded from `https://www.apache.org/licenses/LICENSE-2.0.txt`. Never type or paraphrase it from memory. Verify GitHub detects it as "Apache-2.0".
3. `NOTICE` file with project name, copyright line (`Copyright 2026 <owner name>`) and third-party attributions required by dependencies.
4. Every source file (`.py`, `.ts`, `.tsx`, `.js`, `.css`, `Dockerfile`, `Makefile`, `.yml`, `.sh`) starts with `SPDX-License-Identifier: Apache-2.0` in the language's comment syntax. `pyproject.toml` declares `license = "Apache-2.0"`; `package.json` declares `"license": "Apache-2.0"`.
5. **Everything committed is covered**: code, docs, configs, examples, generated test audio and reference transcripts are released under Apache-2.0. Nothing enters the repo whose rights the owner cannot grant.
6. README shows the license badge and a "License" section; the Devpost text names the license.

### B. Dependencies stay open and compatible
1. **Allowed** dependency licenses (OSI-approved and Apache-2.0-compatible): Apache-2.0, MIT, BSD-2-Clause, BSD-3-Clause, ISC, 0BSD, Zlib, PSF-2.0/Python-2.0, MPL-2.0 (unmodified), OFL-1.1 (fonts), Unlicense.
2. **Forbidden** in bundled or imported dependencies: GPL-2.0/3.0 and AGPL-3.0 (copyleft incompatible with distributing the project under Apache-2.0), SSPL, BUSL, Commons Clause, Elastic License, any "non-commercial" or "source-available" license, and dependencies with no license. LGPL requires explicit human approval.
3. `make license-check` fails the build on any non-allowed license (Python: `pip-licenses`; frontend: `license-checker` or equivalent) and runs in CI. `THIRD_PARTY_LICENSES.md` is generated from it, never hand-written.
4. **External executables** (ffmpeg, Redis, Docker base images) are invoked as separate programs, never vendored or linked into project code. `THIRD_PARTY_LICENSES.md` documents each one, its license as shipped by the distribution package, and where its source is available.
5. **Hosted services and models** are documented honestly: the Gemini API is a hosted Google service with its own terms (not open source); the code that uses it is. The optional Gemma engine gives a fully open-model path; the model's license is verified at kickoff and stated in the docs.

### C. Brand and third-party assets are NOT relicensed
1. Trademarks and logos (Nerdearla, Google, Gemini, OBS…) are not covered by Apache-2.0 and are **never committed**. Branding is runtime configuration (`branding.yaml`: event name, colors, logo path/URL); `branding/local/` is git-ignored.
2. The default theme is the neutral "Lenguaraz" theme. A Nerdearla example config may reference the official logo page but must not contain the logo files.
3. No third-party audio, video, fonts or images without a compatible license (see also Article I.8).

### D. Documentation: any conference can deploy it without us
1. **Audience of the docs:** a volunteer tech lead at an unknown conference, with Docker and a Google account, who has never seen this repo. No knowledge of Nerdearla or of the authors is assumed.
2. **Event-agnostic product:** no event name, stage, language or brand is hardcoded. Everything is configuration with documented defaults and examples.
3. **Required documentation set** (English; `README.es.md` and `docs/es/quickstart.md` in Spanish):

| File | Must answer |
|---|---|
| `README.md` | What it is, 60-second pitch, screenshot/GIF, **3-command quickstart**, requirements, credentials and models needed, links to all docs, license badge |
| `docs/deploy/quickstart.md` | Laptop to live subtitles in ≤15 minutes, including a credential-free **dry-run mode** (`ENGINE=fake`) to try the UI |
| `docs/deploy/production.md` | Single VM with Docker Compose, TLS via reverse proxy, domain, `ADMIN_TOKEN`, sizing, backups of config, upgrades |
| `docs/deploy/scaling.md` | From 2 to 30+ stages: workers, optional Redis, API quota planning (per-project limits, concurrent Live sessions, spend limits per tier), capacity table from the simulator |
| `docs/deploy/audio-sources.md` | How to feed audio: file, HLS, RTMP, SRT, OBS/vMix output, local mic/tab; copy-paste ffmpeg examples; latency tips |
| `docs/configuration.md` | Every env var and every `stages.yaml` / `branding.yaml` field: type, default, example, validation |
| `docs/operations/runbook.md` | Event-day checklist (T-24h, T-1h, during, after), incident playbooks (stage DEGRADED, 429 quota, network loss, wrong language, bad glossary), exporting transcripts |
| `docs/customization.md` | Languages, glossaries, auto-glossary, branding, OBS overlay parameters |
| `docs/cost.md` | Cost formula (stages × hours × languages), measured numbers with pricing date, worked example for a 3-track, 2-day event |
| `docs/architecture.md` | Diagram, components, data flow, event contract |
| `docs/security.md` + `SECURITY.md` | Threat model summary, key handling, ephemeral tokens, admin auth, reporting vulnerabilities |
| `docs/privacy.md` | What data flows where, retention, paid-tier recommendation, 18+ operator notice |
| `docs/troubleshooting.md` | Top symptoms → cause → fix |
| `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (original short text linking to Contributor Covenant), `CHANGELOG.md` | How others extend and maintain it |
| `examples/` | `stages.minimal.yaml`, `stages.multitrack.yaml`, `branding.example.yaml`, `.env` profiles |

4. **Docs are code:** every command in the docs is copy-pasteable and tested. `make docs-check` validates links and that every config key in code appears in `docs/configuration.md` (and vice versa).
5. **Fresh-clone test** (`make fresh-clone-test`): clone the public repo into an empty temp dir, follow `quickstart.md` literally in dry-run mode, reach `/healthz` OK and see captions in the audience view. It must pass before `v0.2.0` and `v1.0.0`.
6. **Docs-as-you-go:** every feature's Definition of Done includes updating the affected docs. Documentation is never left for the end.

## Article XVIII — Governance

1. Amendments require explicit human approval, a version bump (semver) and a changelog entry below.
2. The agent may **propose** amendments when a principle blocks a better solution; it never applies them unilaterally.

### Changelog
- 1.0.0 — Initial ratification at kickoff. Includes Article XVII (OSI license & universal deployability).
- 1.0.1 — 2026-09-24T22:45Z: naming convention amended by the owner (N1): standard English surface names; product name unchanged.
