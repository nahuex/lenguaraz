# Devpost submission text (draft for H5)

The owner pastes these sections into the Devpost form. Numbers come from `docs/metrics.md`,
`docs/scale-report.md` and `docs/cost.md` as measured on 2026-09-24; update them if you
re-measure before submitting.

## Project name

Lenguaraz

## Tagline

Live captions and translation for every stage of a conference, in the language each person
chooses — open source, on the Gemini Live API.

## Inspiration

Multi-track conferences lose part of their audience at every talk: people who don't follow
the speaker's language, people who can't hear well, remote viewers on a noisy connection.
Human interpreters are wonderful and scarce; captions on one screen serve one room. We
wanted every attendee to open a page on their phone, pick a stage and a language, and read
the talk as it happens. The name is Rioplatense Spanish: a *lenguaraz* was the interpreter
who travelled with the expeditions across the Pampas.

## What it does

- Transcribes every stage in real time with `gemini-3.5-transcribe-live` over the Live API:
  partial captions while the speaker talks, a committed line at every pause, per-talk
  glossary biasing (`custom_vocabulary`) so names and acronyms come out right.
- Translates the finals (and, progressively, long partials) into any number of target
  languages with `gemini-3.5-flash-lite`, glossary-aware and with context, only for the
  languages someone is actually listening to.
- Serves the audience view (**Live captions**: stage and language picker, font size, high
  contrast, dark mode, screen-reader friendly), an OBS/vMix browser source (**Overlay**) and an
  operator dashboard (**Admin**: state, latency percentiles, rotations, cost, start/stop,
  SRT/VTT/TXT export).
- Survives the 10-minute Live session limit with make-before-break rotation at a pause (0 lost,
  0 duplicated sentences measured), reconnects with backoff, degrades to source text when
  translation fails, and reopens a session that goes silent while speech keeps flowing.
- Builds a first glossary automatically from the talk title and abstract with Gemini
  structured output (**auto-glossary**), merged after the operator's manual list.
- Runs many stages in one process (10 stages ≈ 10 % of one core), any audio ffmpeg can read
  (SRT, RTMP, HLS, files), non-root read-only container, and a credential-free dry-run mode.

## How we built it

Spec-driven development with a written constitution and an agentic engineering loop
(spec → plan → tasks → red/green/verify/commit), in the 24-hour window of the hackathon.
Python 3.12 + FastAPI + asyncio (one `TaskGroup` per stage, bounded queues, never drop a
final), the official `google-genai` SDK with every API field verified against the Gemini
docs, Vite + React + Tailwind for the pages, ffmpeg for ingest. Every claim in the README is
measured by a script in the repo: `make smoke-stt` (WER, first-partial and utterance-to-final
latency), `make smoke-translate`, `make simulate` (10 stages, CPU/RSS/cost) and
`make mvp-check` (7 gates, fake and real engine).

## Challenges we ran into

- Server-side voice activity detection finalized sentences late (p95 15 s on our clips);
  a hybrid VAD (client-side silence → `audio_stream_end`) brought utterance-to-final to
  ~0.9 s p50 with 7/7 finals.
- Rotating a Live session without losing words: the first version switched mid-sentence
  (WER 32 %); switching at the next detected pause and draining the old session fixed it.
- The transcription session sends no usage metadata, so cost is estimated from audio
  seconds and response characters, and documented as such.
- Live API variance: one run in ~15 stalled silently; we added a stall watchdog instead of
  hiding the row in the metrics table.
- A TTS sample at 48 kHz mislabeled as 24 kHz produced a half-speed clip that the STT could
  not follow; the generator now trusts the mime type.

## Accomplishments that we're proud of

Measured numbers instead of promises: WER 3.2 % (EN) / 4.3 % (ES) on technical clips,
utterance-to-final p50 ≈ 0.9 s, translation time-to-first-token ≈ 0.6 s, 0 lost / 0
duplicated sentences across forced rotations, USD 0.495 per stage-hour, ten stages at 10 %
CPU. And a documentation set that lets a conference we have never met deploy it alone,
verified by `make fresh-clone-test`.

## What we learned

The Live API rewards clients that shape the conversation: hybrid VAD, glossary priming and
pause-aligned rotation mattered more than any prompt. Structured output makes small helper
calls (the auto-glossary) reliable. And writing the docs as we went was cheaper than writing
them at the end.

## What's next for Lenguaraz

Spoken interpretation (`gemini-3.5-live-translate-preview`) as an audio channel for large
audiences, browser-side audio ingest for small events, a Redis event bus for multi-worker
deployments, and an offline Gemma fallback for venues with poor connectivity — all already
specified in the backlog.

## Built with

python, fastapi, asyncio, google-genai, gemini-3.5-transcribe-live, gemini-3.5-flash-lite,
gemini-3.8-flash-tts, react, typescript, vite, tailwindcss, ffmpeg, docker, github-actions,
trivy, gitleaks, syft

## Links

- Repository: https://github.com/nahuex/lenguaraz (Apache-2.0)
- Video: (YouTube link, added at H5)
- Docs: `docs/deploy/quickstart.md`, `docs/metrics.md`, `docs/scale-report.md`, `docs/cost.md`
