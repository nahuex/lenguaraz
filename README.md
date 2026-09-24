# Lenguaraz

*The open-source interpreter for every stage.* Pronounced *len-gwa-RAHS*.

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

Lenguaraz turns the audio of every stage of a conference into live captions, in the language
being spoken and translated into the languages the audience asks for. One YAML file describes
the stages, one command starts everything, and each attendee opens a link on their phone,
picks a stage and a language, and reads.

On the 18th–19th century Río de la Plata frontier, the *lenguaraz* was the interpreter who
stood between peoples who did not share a language, so that everyone in a parley could follow
what was said. That is exactly this system's job: someone speaks on a stage, and every person
understands it in their own language.

> **Status:** built during the Nerdearla Vibeathon 2026 window (2026-09-24 15:00 UTC →
> 2026-09-25 15:00 UTC). Features land in order; this README says what works today.

## What it does today

- **Live transcription** of any audio source a conference already has (file, HLS, RTMP, SRT,
  or a device) with Google's `gemini-3.5-transcribe-live` over the Live API: partial captions
  while the speaker talks, a committed line at every pause, per-stage glossary biasing.
- **Many stages at once**, each in its own isolated pipeline with a visible state
  (`IDLE · STARTING · LIVE · ROTATING · DEGRADED · STOPPED`) and automatic reconnection.
- **Audience view (Fogón):** stage and language picker, font size, high contrast, dark mode,
  screen-reader friendly captions, reconnecting WebSocket.
- **Dry-run mode** (`ENGINE=fake`) that exercises the whole UI without credentials.
- **Measured latency**, not claimed: `make smoke-stt` reports word error rate, first-partial and
  utterance-to-final latency percentiles and token usage against bundled samples with known
  sentence boundaries (`docs/metrics.md`).

Translation fan-out, seamless session rotation, the operator panel, overlays and transcript
export follow in the next features (see the backlog in `.specify/memory/product.md`).

## Quickstart (3 commands)

```bash
git clone https://github.com/nahuex/lenguaraz.git && cd lenguaraz
cp .env.example .env      # set GEMINI_API_KEY=… (or ENGINE=fake for a credential-free dry run)
docker compose up --build
```

Then open http://localhost:8000 and click **Open Fogón** on a stage. Full walkthrough,
developer path and troubleshooting: [docs/deploy/quickstart.md](docs/deploy/quickstart.md).

**Requirements:** Docker (or Python 3.12 + [uv](https://docs.astral.sh/uv/) + Node 24 +
ffmpeg for the developer path). **Credentials:** one Gemini API key from
[Google AI Studio](https://aistudio.google.com/), kept server-side in `.env`; use a project
with billing enabled for real events. **Models** (all configurable): `gemini-3.5-transcribe-live`
(captions), `gemini-3.5-flash-lite` (translation), `gemini-3.8-flash-lite-tts` (test audio).

## Naming

Components carry names from the lenguaraz's world on the surface (UI, routes, metrics, docs)
and descriptive technical names in the code:

| Surface name | Component | Code module | Meaning |
|---|---|---|---|
| **Oído** (`oido`) | Audio ingest (ffmpeg / browser) | `ingest/` | "The ear" — listens to the stage |
| **Lengua** (`lengua`) | Live transcription | `stt/` | "Tongue / language" — turns voice into words |
| **Parla** (`parla`) | Text translation fan-out | `translate/` | Rioplatense for "the gift of speech" — says it in every language |
| **Posta** (`posta`) | Make-before-break session rotation | `stt/rotation.py` | Relay stations where messengers changed horses without stopping the message |
| **Baqueano** (`baqueano`) | Language-demand reconciler (D8) | `translate/demand.py` | The guide who knows which paths to open and which to close |
| **Chasque** (`chasque`) | Event bus and audience fan-out | `bus/` | The messenger who carries the word to everyone |
| **Fogón** (`/fogon/{stage}`) | Audience view | `web/src/pages/Fogon.tsx` | The campfire where people gather to listen |
| **Mangrullo** (`/mangrullo`) | Production monitoring & admin | `web/src/pages/Mangrullo.tsx`, `api/admin.py` | The frontier watchtower — sees everything |
| **Pizarrón** (`/pizarron/{stage}`) | OBS/vMix overlay | `web/src/pages/Pizarron.tsx` | The general store's chalkboard, visible to all |
| **Diccionario** (`diccionario`) | Glossary + auto-glossary | `glossary/` | The lenguaraz's knowledge |
| **Acta** (`acta`) | SRT/VTT/TXT export | `export.py` | The written record of the parley |

## Architecture in one picture

```
stages.yaml ─▶ one isolated pipeline per stage:
  Oído (ffmpeg / WAV) ─▶ Lengua (Gemini Live STT, interim + final) ─▶ Chasque (bus) ─▶ WS /ws/{stage}?lang=
                                                                                        └▶ Fogón (audience)
```

Details, event contract and endpoints: [docs/architecture.md](docs/architecture.md).
Every setting and every `stages.yaml` field: [docs/configuration.md](docs/configuration.md).

## Test audio

`samples/` ships two short talks generated with Gemini TTS from original scripts written for
this project (English: Kubernetes and eBPF; Spanish: Python asyncio), with reference
transcripts and exact sentence boundaries. They are released under Apache-2.0 like everything
else here. Regenerate them with `make samples`.

## Security & privacy

The Gemini API key lives only on the server. Audience endpoints are read-only and rate-limited
per IP. Audio is never written to disk; captions live in a bounded in-memory buffer and are
only logged when `LOG_TRANSCRIPTS=true`. The Gemini API requires operators to be **18 or
older** and deployments must not be directed at minors. On the unpaid tier Google may use
content to improve its products; use a **paid-tier project** for real events.

## How this repo is built

Spec-driven development with an AI engineering crew and one human owner: every feature goes
`spec.md → plan.md → tasks.md → implementation loop`, with a constitution as supreme law.
See [CLAUDE.md](CLAUDE.md), the [constitution](.specify/memory/constitution.md), the
[ground truth](.specify/memory/ground-truth.md) of verified API facts and the
[product brief](.specify/memory/product.md). Decisions are logged in
[docs/decisions.md](docs/decisions.md).

## License

Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE). Gemini is a hosted Google
service with its own terms; the code that talks to it is open source.
