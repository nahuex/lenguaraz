# Ground Truth — Verified Technical Facts

> Verified against official sources on 2026-09-22. **Re-verify at kickoff** (task T-000) with the Gemini Docs MCP; if anything drifted, fix this file first and note it in the changelog at the bottom. Plans cite these facts by section number (e.g., `GT-2.3`).

## GT-1 Challenge rules (nerdearla26.devpost.com — Overview, Rules, Resources)
1. Window: 2026-09-24 15:00 UTC → 2026-09-25 15:00 UTC. Projects started before the window are not considered.
2. Existing libraries/models/services allowed (Gemini, Gemma, Whisper…); the solution must be your own.
3. Required: working project; 1–2 min YouTube demo with real audio from a past Nerdearla talk; public repo with OSI license; README with how to run + credentials/models needed.
4. MVP: live audio from ≥1 source (mic/file/stream; include test audios + easy import); real-time transcription of original (ES or EN); real-time translation EN→ES; subtitles shown anywhere; ≥2 simultaneous sessions + README on scaling.
5. Challenge also asks: multi-session at scale (5, 10+ stages), audience web/app to choose session and language, OSI license and clear docs so any conference can deploy.
6. Optional extras: OBS/vMix integration (burn subtitles), more languages (e.g., Portuguese), technical glossary & proper names, full transcript export (SRT/VTT/text), production monitoring panel (status, latency, errors).
7. Recommended: build on Gemini audio capabilities; Gemma for 100% local.
8. Judging: Quality · Latency · Scalability · Deployment & operation · Innovation.
9. Judges: Nerdearla organizers (2), Google DeepMind Developer Experience (2), Cline (1). Some judges don't speak Spanish → video EN subtitles made with the project itself.
10. Participants must also be registered at Nerdearla before the close. Nerdearla may use/adapt/fork/deploy submissions under their license. Code of conduct applies.

## GT-2 Live transcription (ai.google.dev/gemini-api/docs/live-api/live-transcribe)
1. Model: `gemini-3.5-transcribe-live`. Live API over WebSockets or Gen AI SDK. `response_modalities=["TEXT"]`.
2. Config `input_audio_transcription`: `language_codes` (BCP-47; empty = auto-detect incl. code-switching), `custom_vocabulary` (up to 1,000 terms; best results ≤100), `mode` = `VERBATIM` (default) | `SMART` (removes disfluencies, formats; not combinable with word annotations).
3. Server events: `server_content.interim_input_transcription` (fast partial hypotheses) and `server_content.input_transcription` (final, on pause/turn end).
4. VAD: automatic (default); hybrid (client sends `audio_stream_end` on local silence → fast finalization, server VAD as fallback); manual (`automatic_activity_detection.disabled=true` + `activity_start/end`).
5. Limits: continuous streaming up to **10 minutes** per session; **no speaker diarization** in live; utterance-level timestamps only.
6. Languages include `en-US`, `en-GB`, `es-419`, `es-US`, `pt-BR`, `pt-PT` and 70+ more.
7. Ephemeral tokens supported (`auth_tokens.create` with `uses`, `expire_time`, `live_connect_constraints`).

## GT-3 Audio format
1. Input: raw 16-bit PCM, **16 kHz**, mono, little-endian. MIME `audio/pcm;rate=16000`.
2. Chunks of ~100 ms for transcription/translation (= 3,200 bytes at 16 kHz mono s16le). *Re-verified 2026-09-24:* the live-transcribe guide says "Send audio in chunks of 100ms (1,024 to 2,048 frames)" and the live-translate guide says "Send audio in chunks of 100ms"; 3,200 bytes = 1,600 frames is our derivation and sits inside that range.
3. Output audio (interpreter mode only): raw 16-bit PCM, 24 kHz, mono.

## GT-4 Live translation (…/live-api/live-translate)
1. Model: `gemini-3.5-live-translate-preview`. Speech-to-speech, 70+ languages, continuous (no turn waiting).
2. Config: `response_modalities=["AUDIO"]`, `input_audio_transcription`, `output_audio_transcription`, `translation_config{target_language_code, echo_target_language}` (echo default false = silent if input already in target).
3. **No tools, no system instructions** → no glossary control. Audio input only.
4. Ephemeral tokens can lock `translation_config` server-side.

## GT-5 Sessions (…/live-api/session-management)
1. Audio-only session without compression: 15 min. **Connection lifetime ~10 min.**
2. Server sends `GoAway` with `time_left` before closing.
3. `session_resumption` gives handles (valid 2 h after termination); `context_window_compression` (sliding window) extends conversational sessions. Applicability to the transcription model must be verified; rotation strategy must not depend on it.

## GT-6 Pricing, paid tier (ai.google.dev/gemini-api/docs/pricing, read 2026-09-22)
1. `gemini-3.5-transcribe-live`: input $3.50/1M audio tokens (~$0.005/min), output $21/1M text (~$0.004/min) → **~$0.009/min ≈ $0.54 per stage-hour** (25 audio tokens/s, ~175 text tokens/min).
2. `gemini-3.5-live-translate-preview`: **~$0.0368/min ≈ $2.21 per stage-hour per target language**.
3. `gemini-3.5-flash-lite` (described as optimized for high-volume tasks and translation): $0.30/1M input, $2.50/1M output. Translation cost per language is small relative to STT; compute from measured `usage_metadata`.
4. Free tier: content used to improve Google products. Paid tier: not used.
5. TTS for generated test audio (read 2026-09-24, paid tier per 1M tokens): `gemini-3.8-flash-tts` input $0.50 (text) / output $9.00 (audio) through 2026-12-31 (then $1.00 / $18.00); `gemini-3.8-flash-lite-tts` input $0.50–1.00 / output $6.00–12.00. Audio output = 25 tokens per second, so a 60 s clip ≈ 1,500 audio tokens ≈ $0.01–0.02. Negligible for `make samples`.

## GT-7 Rate limits (…/rate-limits)
1. Limits are **per project**, not per key. Preview/experimental models are more restricted. Check active limits (incl. concurrent Live sessions) in AI Studio.
2. Spend-based limits per rolling 10 min: Tier 1 $10, Tier 2 $50, Tier 3 $200 → `429 RESOURCE_EXHAUSTED`.
3. The rate-limits page publishes **no concurrent Live session figure per tier** (re-verified 2026-09-24); the only concurrency number there is for Batch. The active per-project limit is visible only in AI Studio → H0-4 default (Tier 1, 2–4 real stages) stands until the owner reads it there.

## GT-8 Terms (ai.google.dev/gemini-api/terms)
1. 18+ to use the APIs; API clients must not be directed at or likely accessed by under-18s.
2. Use only in available regions. No competing-model development. Prohibited Use Policy applies. Don't bypass safety.

## GT-9 Agent tooling (ai.google.dev/gemini-api/docs/coding-agents)
1. Gemini Docs MCP: `npx add-mcp "https://gemini-api-docs-mcp.dev"` → tool `search_documentation`. Verify in Claude Code with `/mcp`.
2. Skills: `npx skills add google-gemini/gemini-skills --skill gemini-live-api-dev` and `--skill gemini-api-dev`. Verify with `/skills`. The `gemini-api-dev` skill steers text generation toward the **Interactions API** and current model IDs.

## GT-10 Open models
1. Gemma 4 family (Apache-2.0). Gemma 4 E4B: compact model with native speech recognition and translation. Gemma 4 12B: mid-size with native audio input. TranslateGemma: open translation-focused models. Used only for the optional offline engine.
2. Re-verified 2026-09-24 on the Gemma 4 model card (ai.google.dev/gemma/docs/core/model_card_4): license "Apache 2.0" (ai.google.dev/gemma/apache_2); native audio (ASR + speech-to-translated-text) only on **E2B, E4B and 12B Unified** (not 26B A4B / 31B); E4B = 4.5B effective (8B with embeddings), 128K context; 12B Unified = 11.95B, 256K context. TranslateGemma released 2026-01-15 in 4B/12B/27B; its license is **not stated on ai.google.dev** → verify on its model card before any use (feature 011 only).

## GT-13 Model IDs (ai.google.dev/gemini-api/docs/models, read 2026-09-24)
| Role | Model ID | Status on models page | Env var |
|---|---|---|---|
| Live transcription (STT) | `gemini-3.5-transcribe-live` | Stable (unary/file variant: `gemini-3.5-transcribe`) | `GEMINI_STT_MODEL` |
| Text translation | `gemini-3.5-flash-lite` | Stable ("fastest, most cost-effective 3.5 model for high-throughput execution") | `GEMINI_TRANSLATE_MODEL` |
| Spoken interpreter | `gemini-3.5-live-translate-preview` | Preview | `GEMINI_INTERPRETER_MODEL` |
| TTS for test audio | `gemini-3.8-flash-lite-tts` (default; "fast, cost-efficient workhorse") · `gemini-3.8-flash-tts` (max fidelity) | Stable; `gemini-3.1-flash-tts-preview` and `gemini-2.5-*-tts` are legacy | `GEMINI_TTS_MODEL` |

Speech-generation guide (…/speech-generation): both 3.8 TTS models share the same API schema; Flash TTS covers 130 languages, Flash-Lite TTS 101; single- and multi-speaker supported.

## GT-11 Open source licensing (opensource.org/licenses, read 2026-09-22)
1. Challenge text: the solution must be under a license approved by the Open Source Initiative **and** have clear documentation so that any conference can deploy it. Submission rules also accept "MIT, Apache 2.0, GPL or similar".
2. Apache License 2.0 is listed as OSI Approved, SPDX `Apache-2.0`, category "Popular / Strong Community". MIT, BSD-2/3-Clause, MPL-2.0, GPL-2.0/3.0, AGPL-3.0, ISC, 0BSD, Zlib and Unlicense are also listed.
3. Official Apache-2.0 text: `https://www.apache.org/licenses/LICENSE-2.0.txt` (copy verbatim).
4. Gemini API Additional Terms: Google does not claim ownership of generated content (relevant for TTS-generated test audio released under the repo license).

## GT-12 Field lessons from prior art (see prior-art.md)
1. Google's broadcast translation app reports that the Gemini **free tier limits concurrent Live WebSocket connections to roughly 3–5**; multi-language/multi-stage events require a paid tier (Tier 1–3) key.
2. Same source: an in-memory session manager forces a single instance; horizontal scale needs coordination such as Redis.
3. Google's CLI translate example streams a remote audio URL into Live Translate; a Google-hosted sample WAV exists for smoke tests (reference by URL only).

## Changelog
- 2026-09-22 — compiled (incl. GT-11 licensing).
- 2026-09-24T15:40Z — T-000 re-verification against the official pages on ai.google.dev (Gemini Docs MCP loads only after the session restart; the MCP re-check is queued for the 001 plan). Method: one independent fetch agent per section grading every claim, plus an adversarial re-fetch for each claim graded drifted/unverifiable (14 agents, 108 tool calls). Result: **GT-2, GT-4, GT-5, GT-6.1–4, GT-7.1–2 and GT-8 confirmed verbatim; no drift.** Added: GT-3.2 chunk-size clarification, GT-6.5 TTS pricing, GT-7.3 (no published concurrent-session figure), GT-10.2 (Gemma 4 license/audio details, TranslateGemma license unverified), GT-13 model-ID table incl. `GEMINI_TTS_MODEL`.
