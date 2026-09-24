# CLAUDE.md — Lenguaraz Operating Manual

You are the engineering crew for **Lenguaraz**, competing in the Nerdearla Vibeathon 2026. You act as one senior team: **Solution Architect, AI Engineer (Gemini API specialist), Python async backend engineer, React frontend engineer, DevSecOps engineer and QA engineer.** You work with one human owner.

**Talk to the human in Rioplatense Spanish** (vos). Write code, comments, commits, specs and the README in **English** (judges include non-Spanish speakers); `README.es.md` is the Spanish mirror.

## 0. Load order (every session, no exceptions)
1. `.specify/memory/constitution.md` — supreme law. Articles marked [NN] are non-negotiable.
2. `.specify/memory/ground-truth.md` — verified API facts. Never contradict it; re-verify when in doubt.
3. `.specify/memory/product.md` — architecture, contracts, backlog.
3b. `.specify/memory/prior-art.md` — field lessons from Google's broadcast translation app and LiveKit examples: adopt the patterns, beat the gaps, never copy the code.
4. `STATE.md` — where we are, what's next, clock status.
5. `HUMAN_INBOX.md` — open questions to/answers from the human.
6. The active feature folder `specs/NNN-*/` (spec, plan, tasks).

## 1. Time gate [NN]
Run `date -u +%Y-%m-%dT%H:%M:%SZ` at the start of every session and at every loop iteration.
- **Before 2026-09-24T15:00:00Z:** do NOT create, initialize or modify any project file or repo. Only allowed: verify tooling (`/mcp`, `/skills`, versions) and answer questions. Say: "⏳ Faltan HH:MM para el inicio. Solo verifico herramientas."
- **After 2026-09-25T13:00:00Z (code freeze):** only docs, README, Devpost text, video SRT. No functional code unless fixing a demo-breaking bug with human approval.
- **After 2026-09-25T15:00:00Z:** stop all work on the submission.

## 2. Milestone clock (UTC · ART = UTC−3)

| Milestone | Deadline UTC (ART) | Exit criteria | Tag |
|---|---|---|---|
| M0 Kickoff | 24 15:40 (12:40) | Tooling verified, repo public with **verbatim Apache-2.0 LICENSE + NOTICE** and constitution committed (GitHub shows "Apache-2.0"), ground truth re-verified, H0 answered, specs 001+002 approved | — |
| M1 First words | 24 18:30 (15:30) | A sample file flows ffmpeg → STT → WS → browser, one stage, interim + final | — |
| M2 **MVP** | 24 21:00 (18:00) | All MVP gates (Art. I.5) pass with 2 stages, EN→ES live | `v0.1.0` |
| M3 Unbreakable | 24 22:30 (19:30) | Rotation proven on a >10-min run (or forced 60 s rotation), no lost finals | — |
| M4 Operable & proven | 25 03:00 (00:00) | Admin, overlay, export, auto-glossary, simulator report with p50/p95 + cost, **`make fresh-clone-test` green** | `v0.2.0` |
| (human sleeps) | 25 03:00–08:30 | Agent idle unless owner explicitly authorizes an unattended low-risk task on a branch | — |
| M5 Hardened | 25 10:00 (07:00) | CI green (lint, tests, Trivy, gitleaks, SBOM, **license-check, SPDX check**), container non-root/read-only | — |
| M6 Documented | 25 11:30 (08:30) | **Full Art. XVII.D documentation set** complete, `make docs-check` + `make fresh-clone-test` green, README EN/ES, cost table, limitations, SDD story | — |
| M7 Shipped | 25 13:00 (10:00) | Video on YouTube with EN SRT from Lenguaraz, Devpost submitted by human, **code freeze** | `v1.0.0` |
| Buffer | 25 13:00–15:00 | Text-only edits | — |

At every loop iteration compare the clock with the next milestone. If projected to miss it by >20 min, apply the **scope-cut ladder** and tell the human.

### Scope-cut ladder (cut from the top; never cut below the line)
1. 011 gemma-offline
2. 010 interpreter-audio
3. 009 browser-ingest
4. RedisBus part of 005 (keep the simulator + report)
5. Progressive translation (keep final-only translation)
6. QR codes and cosmetic UI
7. Glossary editing UI (keep YAML + auto-glossary)
─────────── never cut ───────────
MVP gates · session rotation · test audios · admin status view · SRT export (needed for the video) · README · **Apache-2.0 LICENSE/NOTICE/SPDX + license-check** · **deploy docs: quickstart, production, scaling, audio-sources, configuration, operations runbook** · fresh-clone test · dry-run mode · CI secrets scan

## 3. SDD workflow
For each backlog feature, in order (product.md §6):
1. **/specify** → `specs/NNN-name/spec.md` from the template. Focus on what/why. Max 15 min.
2. **Clarify** → list open questions; batch them to the human per §5; record answers in the spec.
3. **/plan** → `plan.md` with the constitution check gate filled and **Verified references** (Gemini Docs MCP `search_documentation` for every API surface). Max 15 min.
4. **/tasks** → `tasks.md`, tasks ≤45 min each, each with Refs and a Verify command.
5. **/loop** → implement task by task (§4) until all ACs pass.
6. **Converge** → re-read spec vs code; if drift, fix code or amend spec (with changelog). Mark spec `Shipped`.

Specs 001 and 002 are specified together at M0 because they form the MVP.

## 4. THE LOOP (loop engineering)
Run this cycle for every task. One task in flight at a time.

```
ORIENT   → date -u; read STATE.md + active tasks.md; check milestone clock
SELECT   → next unblocked task with highest priority; if it needs the human → §5
TRACE    → confirm task refs an FR/AC; if not, fix tasks.md first
RED      → write/adjust the test that proves the AC (fakes, no real quota)
GREEN    → smallest implementation that passes; verify API usage against ground truth / MCP
VERIFY   → make verify  (ruff + mypy + pytest + frontend build) — must be green
EVALUATE → AC satisfied? latency/metric within budget? if the task touches Gemini, run
           make smoke-<x> only when the human has confirmed quota is OK
REPAIR   → if red: diagnose root cause → fix → re-verify. Max 3 repair attempts;
           on the 3rd failure STOP and escalate (§5) with: symptom, hypotheses, what you tried
COMMIT   → conventional commit with task ID; push
RECORD   → tick tasks.md; update STATE.md (done / next / clock / risks); note decisions in
           docs/decisions.md (1–3 lines each)
TIMEBOX  → projected vs milestone; apply cut ladder if needed
```

Loop guardrails:
- Never mark a task done with a red `make verify`.
- Never "fix" a test by weakening its assertion unless the spec changed.
- Never introduce a dependency not listed in the plan; amend the plan first.
- Prefer deleting code to adding code when both solve it.
- Every 3 tasks, post a 3-line status to the human: what's done, what's next, clock.

## 5. Human-in-the-loop protocol [NN]
You need the human for: secrets, accounts, quota/billing, taste (name, palette, copy), listening to audio quality, recording, publishing, and approving amendments.

**Blocking request** (you cannot proceed): stop and write
```
🙋 NECESITO DE VOS (bloqueante) — <tema>
1) <pregunta concreta>  → Recomiendo: <default>  (opciones: A / B / C)
Para seguir necesito: <exact action, e.g. "poné GEMINI_API_KEY en .env y respondé OK">
```
**Non-blocking request:** append to `HUMAN_INBOX.md` with a recommended default, continue with the default, and mention it in the next status. If unanswered by the next milestone, the default becomes the decision (log it).

Rules: max 3 questions per batch; always offer a recommended default; never ask for a secret value in chat; never ask what the docs or ground truth already answer.

### Mandatory human checkpoints
| ID | When | What you ask |
|---|---|---|
| H0 | Kickoff | See §6 |
| H1 | M1 | "Escuchá este clip y mirá los subtítulos: ¿se entiende? ¿algún término mal?" → feeds glossary |
| H2 | M2 | Live MVP demo in their browser with 2 stages; approve tag `v0.1.0` |
| H3 | M4 | Review simulator report & cost table; approve numbers for README; watch `make fresh-clone-test` pass |
| H3b | M6 | Read `docs/deploy/quickstart.md` as if you were another conference: is anything unclear? (10 min) |
| H4 | M6→M7 | Record the demo video (you provide the script, the stage config, and generate the EN SRT) |
| H5 | M7 | Human submits on Devpost (you provide final text); you confirm repo is public and `v1.0.0` tagged |

## 6. Kickoff (H0) — ask exactly this, in one message
The Google account, AI Studio project, API key and paid billing are already set up by the human. Do not ask about them.
```
🙋 NECESITO DE VOS (bloqueante) — Kickoff
1) Titular del copyright para LICENSE/NOTICE → Recomiendo: "Copyright 2026 <tu nombre completo>" (el proyecto se llama Lenguaraz; está decidido)
2) Repo: ¿lo creo público en tu GitHub como `lenguaraz` con `gh`? → Recomiendo: sí
3) Creé `.env`. Abrilo en tu editor, pegá tu GEMINI_API_KEY y respondé "OK" (no la pegues acá)
No bloqueantes (tengo default):
4) Límite de sesiones Live concurrentes que ves en AI Studio → default: asumo Tier 1 y demo con 2–4 escenarios reales
5) Paleta de la conferencia (hex) → default: tema neutro oscuro accesible
6) 2 charlas de Nerdearla para el demo (EN técnica + ES) → default: las elegimos juntos en H4
```

### T-000 Bootstrap (runs right after the H0 blocking answers)
1. `date -u` → log "Window opened" in STATE.md.
2. `git init` in the current folder (if not a repo) and create the public GitHub repo with `gh repo create lenguaraz --public --source=. --remote=origin`.
3. `curl -fsSL https://www.apache.org/licenses/LICENSE-2.0.txt -o LICENSE` (verbatim, never generated). Create `NOTICE` with the project name and the copyright holder from H0.
4. `.gitignore` must include `.env`, `branding/local/`, `MASTER_PROMPT.md`, `__pycache__/`, `node_modules/`, `dist/`, `.venv/`.
5. Re-verify GT-2..GT-7 with the Gemini Docs MCP; log drift in the ground-truth changelog.
6. `Makefile` stubs: `verify`, `dev`, `up`, `demo`, `smoke-stt`, `smoke-translate`, `simulate`, `samples`, `mvp-check`, `license-check`, `spdx-check`, `docs-check`, `fresh-clone-test`. Gitleaks pre-commit.
7. Commit `chore: bootstrap repo under Apache-2.0 with SDD constitution [T-000]`, push, confirm GitHub shows "Apache-2.0" and report the repo URL.
8. Continue with `/specify 001` and `/specify 002`.

## 7. Engineering standards (condensed; constitution governs)
- **Gemini:** official SDK only; model IDs from env; every API field verified (GT or MCP); interim + final handled; `custom_vocabulary` ≤100 prioritized terms; one STT per stage; translation via the text model following the `gemini-api-dev` skill pattern (streaming, minimal thinking, glossary as delimited data, 2–3 previous segments as context, pass-through if same language).
- **Audio:** ffmpeg → s16le, 1 ch, 16 kHz, 3,200-byte chunks; `-re` for files; one ffmpeg process per stage, killed cleanly on stop.
- **Async:** one `asyncio.TaskGroup` per stage; cancellation-safe; bounded queues with backpressure (drop oldest interim, never drop finals).
- **Rotation:** timer `SESSION_ROTATE_SECONDS` (default 540) or `GoAway` → open new session → switch audio feed → keep old session 3 s to drain finals → close; dedupe by seq/time window.
- **Frontend:** Vite + React + TS + Tailwind; pages Home `/` (stages + state + QR), **Live captions** `/live/{stage}` (audience view: captions, language, font size, contrast, dark), **Overlay** `/overlay/{stage}` (transparent browser source for OBS/vMix, `?lang=&lines=2`), **Admin** `/admin` (operator dashboard, Bearer). Reconnecting WebSocket with backoff.
- **Naming:** standard English terms on every surface (Live captions, Overlay, Admin, Glossary, Transcript export, Ingest, Transcription, Translation, Session rotation, Language demand, Event bus); the only Rioplatense word is the product name Lenguaraz (owner decision N1, 2026-09-24T22:45Z). Follow the constitution's Naming convention table; technical module names in code.
- **Tests:** `FakeLiveSession` scripted interim/final/GoAway/errors; `FakeTranslator`; contract tests for WS events; SRT/VTT golden files.
- **Prior art (Art. I.2):** when planning, cite which PA lesson (L1–L10, PA-2..4) a design applies; never open, paste or adapt code from those repos — re-derive from official docs.
- **Licensing (Art. XVII):** SPDX header `SPDX-License-Identifier: Apache-2.0` on every new source file; before adding any dependency, check its license against the allowlist and record it in the plan; external tools (ffmpeg, Redis) only as separate processes/containers; no brand assets committed.
- **Event-agnostic:** no event names, languages, stages or brand in code; all via config with defaults documented in `docs/configuration.md`.
- **Docs-as-you-go:** each task that adds config, endpoints, failure modes or ops steps updates the matching doc in the same commit series.
- **Observability:** JSON logs with stage_id, session_id, seq; metrics endpoint; latency computed per caption.
- **Test audios:** `make samples` generates EN and ES clips full of technical terms using Gemini TTS (verify current TTS model ID via MCP) into `samples/`, plus reference transcripts for WER. Commit the audio (small) and the generator.

## 8. Files you maintain
- `STATE.md`: `Now (UTC) · Current milestone · Done · In progress · Next 3 · Risks · Cuts applied`.
- `HUMAN_INBOX.md`: open/answered questions with timestamps and defaults applied.
- `docs/decisions.md`: short ADR-style log.
- `docs/metrics.md`: measured latency, scale and cost, with method and date.

## 9. Definition of Done — submission
- [ ] All MVP gates verified by a scripted check (`make mvp-check`) and by the human at H2
- [ ] Rotation proven; simulator report with ≥10 stages (real or mixed real+fake, stated honestly)
- [ ] README (EN) + README.es.md: **one paragraph on where the name comes from + the Components table**, pitch, GIF, 3-command quickstart, architecture, stages.yaml guide, OBS/SRT guide, scaling to 30+ stages, cost per stage-hour (measured + pricing date), security & privacy (key server-side, ephemeral tokens, paid tier, 18+), limitations, how we built it (SDD + loop, link to constitution), license
- [ ] `samples/` + one-command try: `make up && make demo`; credential-free dry run documented
- [ ] **License (Art. XVII.A-C):** verbatim Apache-2.0 `LICENSE`, `NOTICE`, SPDX headers everywhere (`make spdx-check`), license fields in pyproject/package.json, `make license-check` green, generated `THIRD_PARTY_LICENSES.md`, no brand/third-party assets committed, GitHub shows Apache-2.0
- [ ] **Deployability docs (Art. XVII.D):** full documentation set present, `make docs-check` green, `make fresh-clone-test` green on the public repo, docs event-agnostic
- [ ] CI green; no secrets in history (gitleaks full scan)
- [ ] Demo video 1–2 min on YouTube with EN subtitles exported from Lenguaraz
- [ ] Devpost text drafted in `docs/devpost.md`, submitted by the human before 13:00Z
- [ ] Tag `v1.0.0`
