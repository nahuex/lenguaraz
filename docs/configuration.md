# Configuration

Lenguaraz is configured in two places: **environment variables** (deployment: engine,
models, ports, secrets) and **`stages.yaml`** (the event: stages, sources, languages,
glossaries). Nothing about a specific event is hardcoded.

Every key below is validated at startup; an invalid value stops the process with a message
naming the field. `make docs-check` verifies that this page and the code agree.

## Environment variables

Put them in `.env` (copied from `.env.example`) or in the process environment. Shell
variables override `.env` values, so `ENGINE=fake make dev` starts a dry run without
editing files.

| Variable | Type | Default | Description |
|---|---|---|---|
| `ENGINE` | `gemini` \| `fake` | `gemini` | `gemini` uses the Gemini Live API; `fake` is a credential-free dry run that replays the reference transcripts next to the samples and shows a DRY-RUN badge in every page. |
| `GEMINI_API_KEY` | secret string | *(empty)* | Required when `ENGINE=gemini`. Server-side only; never sent to browsers or written to logs. Create it in Google AI Studio on a project with billing enabled. |
| `ADMIN_TOKEN` | string | `change-me-long-random` | Bearer token for the operator endpoints (Mangrullo, feature 004). Change it before any real event. |
| `GEMINI_STT_MODEL` | model id | `gemini-3.5-transcribe-live` | Live transcription model. |
| `GEMINI_TRANSLATE_MODEL` | model id | `gemini-3.5-flash-lite` | Text model used for translation (feature 002). |
| `GEMINI_INTERPRETER_MODEL` | model id | `gemini-3.5-live-translate-preview` | Speech-to-speech model for the optional spoken interpreter (feature 010). |
| `GEMINI_TTS_MODEL` | model id | `gemini-3.8-flash-lite-tts` | Text-to-speech model used by `make samples` to generate the bundled test audio. |
| `STT_MODE` | `SMART` \| `VERBATIM` | `SMART` | `SMART` removes filler words and formats numbers, lists and punctuation; `VERBATIM` keeps every disfluency. |
| `VAD_MODE` | `hybrid` \| `server` | `hybrid` | `hybrid` detects the end of speech locally (RMS below `VAD_THRESHOLD` for `VAD_SILENCE_MS`) and tells the Live API to finalize the turn at once; `server` relies on the server's own silence timeout (slower, sometimes only at stream end). |
| `VAD_SILENCE_MS` | integer 100–5000 | `500` | Silence after speech before the end-of-turn signal is sent (hybrid mode). |
| `VAD_THRESHOLD` | integer 1–20000 | `300` | RMS level (16-bit scale) below which a 100 ms chunk counts as silence. Raise it for noisy rooms. |
| `SESSION_ROTATE_SECONDS` | integer 30–600 | `540` | Live sessions last about 10 minutes; a new session is opened proactively after this many seconds (and on the server's `GoAway`). |
| `STT_STALL_SECONDS` | integer 0–300 | `20` | Stall watchdog: if speech (chunks above `VAD_THRESHOLD`) keeps arriving but the transcription session sends nothing for this long, the session is closed and reopened (counted as `stalls` in the stage snapshot). `0` disables. |
| `ROTATION_DRAIN_SECONDS` | number 0–30 | `3` | After the audio feed switches to the next Live session, the old one stays open this long to deliver its last final captions (Posta, make-before-break). |
| `ROTATION_SWAP_MAX_WAIT_SECONDS` | number 0–60 | `8` | With hybrid VAD, the audio feed switches to the next session at the next pause so no sentence is split; if no pause is detected within this many seconds the switch happens anyway. |
| `DEDUPE_WINDOW_SECONDS` | number 0–60 | `5` | A final caption whose words match one already published within this window is dropped (late duplicates from the old session). |
| `PROGRESSIVE_TRANSLATION` | boolean | `true` | Translate a debounced partial caption so a provisional translated line appears before the sentence ends; the final replaces it. |
| `PROGRESSIVE_MIN_WORDS` | integer 1–50 | `6` | Minimum words in a partial caption before it is translated progressively. |
| `PROGRESSIVE_DEBOUNCE_MS` | integer 100–5000 | `600` | Minimum time between two progressive translations of the same utterance and language. |
| `ALWAYS_ON_LANGS` | comma-separated short codes | `es` | Languages translated even when nobody is listening (so transcripts and exports exist), restricted to each stage's `targets`. |
| `LANG_GRACE_SECONDS` | number 0–600 | `10` | A language stays active this long after its last listener leaves (Baqueano, D8). |
| `LANG_RECONCILE_DEBOUNCE_MS` | integer 0–5000 | `250` | Documented upper bound for reacting to listener changes; the demand is evaluated at every caption, so a new listener is served by the next final. |
| `TRANSLATE_CONTEXT_SEGMENTS` | integer 0–10 | `3` | Previous (source, translation) pairs sent as context to keep terminology and tense consistent. |
| `TRANSLATE_MAX_OUTPUT_TOKENS` | integer 16–8192 | `512` | Cap on the translation length per segment. |
| `AUTO_GLOSSARY` | boolean | `true` | Before a stage starts, derive technical terms and proper names from `talk.title`/`talk.abstract` (Gemini structured output; a heuristic in dry run) and merge them after the manual `glossary` (manual terms win, 100 max). |
| `AUTO_GLOSSARY_MAX_TERMS` | integer 1–100 | `60` | Maximum terms requested from the auto-glossary. |
| `GEMINI_TRANSLATE_API` | `generate_content` \| `interactions` | `generate_content` | Transport for translation calls. `generate_content` (streaming) measured a 578 ms median time-to-first-token on `gemini-3.5-flash-lite` versus 1407 ms through the Interactions API on 2026-09-24; both are supported by the official SDK. |
| `GEMINI_TRANSLATE_THINKING` | `minimal` \| `low` \| `medium` \| `high` | `minimal` | Thinking level for the translation model; `minimal` gives the lowest latency and cost. |
| `LOG_TRANSCRIPTS` | boolean | `false` | When `true`, caption text is written to the logs. Off by default for privacy. |
| `REDIS_URL` | URL | *(empty)* | When set, the event bus uses Redis so several workers can share stages (feature 005). Empty = in-memory bus, single process. |
| `STAGES_FILE` | path | `stages.yaml` | Path to the stages file. |
| `HOST` | address | `0.0.0.0` | Bind address of the API. |
| `PORT` | integer | `8000` | Port of the API and the audience view. |
| `LOG_LEVEL` | `DEBUG` … `ERROR` | `INFO` | Log level. Logs are JSON lines with `stage_id`, `session_id`, `seq` and `component`. |
| `WS_MAX_CONN_PER_IP` | integer ≥ 1 | `50` | Maximum simultaneous caption sockets per client IP. Raise it when many attendees share a NAT. |
| `FFMPEG_BIN` | path | `ffmpeg` | ffmpeg executable used for non-WAV files and every stream. Local 16 kHz mono WAV files never need ffmpeg. |
| `WEB_DIST` | path | *(auto)* | Folder with the built audience view. Defaults to `web/dist` next to the package (`/app/web/dist` in the container). |

## `stages.yaml`

```yaml
stages:
  - id: main                             # required, lowercase letters, digits and '-', max 32 chars
    name: "Main Stage"                   # required, shown to the audience
    source: "samples/en_kubernetes.wav"  # required: file | http(s) HLS | rtmp:// | srt:// | device
    source_lang: ["en-US"]               # BCP-47 tags; [] = auto-detect (incl. code-switching)
    targets: ["es", "pt"]                # short codes offered to the audience (feature 002)
    talk:
      title: "Observability with eBPF"   # optional, ≤ 200 chars
      abstract: "Kernel-level tracing…"  # optional, ≤ 2000 chars
    glossary: ["Kubernetes", "eBPF"]     # ≤ 100 terms, ≤ 64 chars each
    loop: true                           # replay a file source forever (demo stages)
```

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | string | required | Stage identifier used in URLs (`/fogon/{id}`, `/ws/{id}`). Must be unique. |
| `name` | string | required | Display name (1–80 chars). |
| `source` | string | required | Anything ffmpeg can read: a file path, an HLS URL, `rtmp://`, `srt://`, or a device. See `docs/deploy/audio-sources.md` (feature 008). |
| `source_lang` | list of BCP-47 tags | `[]` | Language hint(s) for the speaker. Empty enables automatic detection, including code-switching. Explicit tags improve accuracy. |
| `targets` | list of short codes | `[]` | Languages the audience can pick in addition to the original (e.g. `es`, `en`, `pt`). |
| `talk.title` | string | `""` | Talk title. Treated as untrusted data when placed in prompts. |
| `talk.abstract` | string | `""` | Talk abstract, same treatment. |
| `glossary` | list of strings | `[]` | Terms the transcription should favour (`custom_vocabulary`, best results ≤ 100) and translation must keep verbatim. |
| `loop` | boolean | `false` | For file sources: start again from the beginning when the file ends. Ignored for streams. |

Examples: `examples/stages.minimal.yaml` (one stage) and the default `stages.yaml` (two
looped sample stages).
