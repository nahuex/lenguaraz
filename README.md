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
- **Live translation (Parla)** into any number of target languages with `gemini-3.5-flash-lite`:
  streamed, glossary-aware, with the previous sentences as context; languages are translated
  only while someone is listening (or listed in `ALWAYS_ON_LANGS`), and a translation failure
  degrades to the source text instead of silence.
- **Seamless session rotation (Posta):** the Live API closes a session after ~10 minutes; the
  next one is opened before that, the switch happens at a pause, and finals are drained and
  de-duplicated. Measured on the real engine: 0 lost, 0 duplicated sentences across forced
  rotations.
- **Operator panel (Mangrullo)** behind a Bearer token: stage table with state, latency and
  cost estimate, start/stop, transcript export as **SRT / VTT / TXT** (Acta) per language.
- **OBS overlay (Pizarrón):** a transparent browser-source page with `?lang=&lines=&size=`.
- **Auto-glossary (Diccionario):** technical terms and proper names derived from the talk title
  and abstract with Gemini structured output, merged after your manual list.
- **Dry-run mode** (`ENGINE=fake`) that exercises the whole UI without credentials.
- **Measured, not claimed:** `make smoke-stt` reports word error rate, first-partial and
  utterance-to-final latency percentiles and token usage against bundled samples with known
  sentence boundaries; `make simulate` runs ten stages in one process and writes a CPU/RSS/cost
  report (`docs/metrics.md`, `docs/scale-report.md`, `docs/cost.md`).

## Quickstart (3 commands)

```bash
git clone https://github.com/nahuex/lenguaraz.git && cd lenguaraz
cp .env.example .env      # set GEMINI_API_KEY=… (or ENGINE=fake for a credential-free dry run)
docker compose up --build
```

Then open http://localhost:8000 and click **Open Fogón · live captions** on a stage. Full walkthrough,
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

## Scaling to more stages

Every stage is one isolated pipeline (one ffmpeg process, one Live transcription session,
one translation worker per active language) inside the same process, so adding a stage is
adding an entry to `stages.yaml`; two stages ship by default and ten look exactly the same.
What grows with the number of stages is (1) CPU for ffmpeg decoding, roughly 2–5 % of a core
per stream, (2) memory, a few tens of MB per stage, and (3) your Gemini project's limit on
concurrent Live sessions, which is per project and tier and visible in Google AI Studio (the
free tier allows only a handful; use a paid-tier project for real events). Beyond one machine,
run several instances, each with its own `stages.yaml` subset, behind any HTTP load balancer
or hostname per instance: stages never share state, and captions are plain WebSocket events
(a shared Redis bus was planned and cut from the hackathon scope; see `docs/decisions.md`).
Cost grows with stages, not with stages × languages: one transcription stream per stage feeds
every language as text. The scale report from `make simulate` (`docs/scale-report.md`: ten
stages, two real and eight simulated, ≈10 % of one core and +18 MB RSS) and the sizing table
in `docs/deploy/scaling.md` put measured numbers on this.

## Technical glossary & proper names

Talks are full of terms that generic speech recognition mangles ("eBPF", "CoreDNS", speaker
and product names). Each stage carries a `glossary` list in `stages.yaml`; Lenguaraz sends it
to the transcription model as `custom_vocabulary` (biasing recognition toward those terms) and
inserts it, clearly delimited, into every translation prompt with the instruction to keep
those terms verbatim. With `AUTO_GLOSSARY=true` (default) the list is extended automatically
from the talk `title` and `abstract` (Gemini structured JSON output; manual terms always win;
100 terms max). `make smoke-stt --glossary none|manual|auto` and `make smoke-translate` report
how often the glossary terms come out right; on the bundled Spanish sample the glossary turned
"task group" into `TaskGroup` and "nerdctl" into `Nerdearla` (`docs/metrics.md`).

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

Everything in this repository was created inside the Vibeathon window (2026-09-24 15:00 UTC to
2026-09-25 15:00 UTC); the git history is the evidence. Before the window opened, the team only
read the challenge rules, the public Gemini API documentation and two public example projects
for lessons; those notes are dated in `.specify/memory/` and contain no code.

Spec-driven development with an AI engineering crew and one human owner: every feature goes
`spec.md → plan.md → tasks.md → implementation loop`, with a constitution as supreme law.
See [CLAUDE.md](CLAUDE.md), the [constitution](.specify/memory/constitution.md), the
[ground truth](.specify/memory/ground-truth.md) of verified API facts and the
[product brief](.specify/memory/product.md). Decisions are logged in
[docs/decisions.md](docs/decisions.md).

## License

Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE). Gemini is a hosted Google
service with its own terms; the code that talks to it is open source.
