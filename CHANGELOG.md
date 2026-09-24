# Changelog

All notable changes to Lenguaraz are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Feature numbers (001–008) and
task ids refer to the specs under `specs/`; the full history is `git log`.

## [Unreleased]

### Added
- **Core pipeline (001):** settings from the environment and a validated `stages.yaml` with
  readable errors; audio ingest (Oído) with a real-time WAV reader and an ffmpeg subprocess
  for any file, HLS, RTMP, SRT or device source, 3,200-byte PCM chunks; Gemini Live
  transcription engine (Lengua) with `custom_vocabulary`, `SMART`/`VERBATIM` modes, interim
  and final segments, `seq`, per-caption latency, reconnect with backoff and `GoAway`
  handling; hybrid VAD (client-side silence sends `audio_stream_end` for fast finals);
  in-memory event bus (Chasque) with bounded queues and drop-oldest-interim backpressure;
  per-stage runner with isolated `TaskGroup`, visible states and p50/p95 metrics; FastAPI
  app with `/healthz`, `/api/stages`, the caption WebSocket (`/ws/{stage}?lang=`, status
  first, close codes 4404/4400/4429/4413, per-IP limit) and SPA serving; `lenguaraz serve`
  CLI with JSON logs; audience view (Fogón) and home page with a reconnecting client, font
  size, contrast, dark mode and a DRY-RUN badge; credential-free dry run (`ENGINE=fake`);
  bundled EN/ES test audio generated with Gemini TTS plus reference transcripts and sentence
  boundaries (`make samples`); `make smoke-stt` with WER, latency percentiles and tokens;
  `make mvp-check` for the seven MVP gates; non-root Docker image and Compose stack.
- **Translation (002):** `TranslationEngine` with a glossary-aware, delimited prompt (data,
  never instructions); Gemini engine with selectable transport (`generate_content` streaming
  or Interactions with `store=False`) and minimal thinking; language demand (Baqueano):
  always-on languages plus languages with a listener, with grace period; ordered per-language
  workers (Parla) with retries, degraded captions on persistent failure and progressive
  translation of debounced partials; translated captions and token usage on the socket and in
  `/api/stages`; `make smoke-translate` in both directions.
- **Resilience (003):** make-before-break session rotation (Posta) on a timer and on
  `GoAway`: the next session opens while the current one listens, the audio feed switches at
  the next pause, the old session drains its finals, late duplicates are dropped, `seq`
  continues and the caption gap is measured; file sources wait for `LIVE`, streams drop the
  oldest audio instead of bursting a backlog; `smoke-stt --rotate`.
- **Operations (004):** in-memory transcript store (Acta) with SRT/VTT/TXT export on the
  audio timeline; operator API and page (Mangrullo) behind `ADMIN_TOKEN` with stage
  snapshots, latency, rotations, errors, duplicates, dropped chunks, token usage and an
  estimated cost from measured usage, start/stop and exports; OBS/vMix overlay (Pizarrón)
  with `lang`, `lines`, `size`, `align` and `bg` parameters; operations runbook.
- **Scale proof (005):** `make simulate` runs N stages in one process (real and simulated
  mix), samples CPU and RSS and writes `docs/scale-report.md` with an honesty note; measured
  cost per stage-hour, worked example and quota planning in `docs/cost.md` and
  `docs/deploy/scaling.md`.
- **Auto-glossary (006):** technical terms and proper names derived from the talk title and
  abstract with Gemini structured output (a heuristic in dry run), merged after the manual
  list (manual wins, 100 terms max); `smoke-stt --glossary none|manual|auto` with measured
  glossary evidence.
- **CI and hardening (007):** GitHub Actions pipeline (ruff, mypy, pytest, frontend tests and
  build, SPDX check, docs check, license gate, gitleaks over the full history, Trivy
  filesystem and image scans, Syft SBOM); `make license-check` with the Apache-2.0-compatible
  allowlist and a generated `THIRD_PARTY_LICENSES.md`; Dependabot; `SECURITY.md`; container
  hardening tests; STT stall watchdog (`STT_STALL_SECONDS`) that reopens a session that goes
  silent while speech keeps flowing.
- **Deployability docs (008, in progress):** `docs/security.md`, `docs/privacy.md`,
  `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` and this changelog.

### Changed
- Hybrid VAD is the default (`VAD_MODE=hybrid`) after measuring utterance-to-final p95 of
  1.1 s versus multi-second finals with server-only VAD (001).
- Translation transport defaults to `generate_content` streaming after measuring a 578 ms
  median time-to-first-token versus 1,407 ms through the Interactions API; the Interactions
  path stays selectable with `GEMINI_TRANSLATE_API` (002).
- Rotation switches the audio feed at the next detected pause instead of as soon as the next
  session is ready, bounded by `ROTATION_SWAP_MAX_WAIT_SECONDS` (003).

### Fixed
- `latency_ms` semantics: interim = gap since the previous partial, final = commit delay;
  speech-to-caption latency is measured against known sentence boundaries by `smoke-stt` (001).
- TTS sample generation read the sample rate from the response mime type (48 kHz vs 24 kHz),
  fixing a half-speed English clip (001).
- A normal close of the old Live session after a swap was misread as the active session
  dying, opening a third session; receiver results are now tied to their session (003).
- A sentence split or lost across a forced rotation; verified 0 lost, 0 duplicated finals (003).

## [0.2.0] — (tag pending owner checkpoint)

Scale and operations milestone: features 003–007 above will move here when the owner
approves the tag after reviewing the simulator report and the fresh-clone test.

## [0.1.0] — (tag pending owner checkpoint)

MVP milestone: features 001–002 above will move here when the owner approves the tag after
the live two-stage demo.

[Unreleased]: https://github.com/nahuex/lenguaraz/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/nahuex/lenguaraz/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/nahuex/lenguaraz/releases/tag/v0.1.0
