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
| `ADMIN_TOKEN` | string | `change-me-long-random` | Bearer token for the operator endpoints (Admin page, feature 004). Change it before any real event. |
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
| `STT_FINAL_TIMEOUT_SECONDS` | number 0–30 | `3` | When the server sends no final within this many seconds after a detected pause (`audio_stream_end`), the last partial is promoted to a final so translation and the transcript keep flowing; a late real final is de-duplicated. `0` disables. Counted as `promoted_finals` in the stage snapshot. |
| `STT_MAX_RECONNECTS` | integer ≥ 1 | `60` | How many consecutive failed connects/reconnects a stage tolerates before it stops (backoff capped at 10 s, so 60 ≈ 10 minutes of a Live API outage, state `DEGRADED` meanwhile). The smoke test uses 5. |
| `TRANSLATE_TIMEOUT_SECONDS` | number 0.1–120 | `10` | A translation call slower than this is abandoned and the caption is published with the original text (`degraded`), so one slow model answer never delays the following sentences. |
| `TRANSLATE_CONCURRENCY` | integer 1–16 | `4` | Final captions translated in parallel per language; results are still published in order. Raises throughput when the model answers slowly. |
| `ROTATION_DRAIN_SECONDS` | number 0–30 | `3` | After the audio feed switches to the next Live session, the old one stays open this long to deliver its last final captions (make-before-break session rotation). |
| `ROTATION_SWAP_MAX_WAIT_SECONDS` | number 0–60 | `8` | With hybrid VAD, the audio feed switches to the next session at the next pause so no sentence is split; if no pause is detected within this many seconds the switch happens anyway. |
| `DEDUPE_WINDOW_SECONDS` | number 0–60 | `5` | A final caption whose words match one already published within this window is dropped (late duplicates from the old session). |
| `PROGRESSIVE_TRANSLATION` | boolean | `true` | Translate a debounced partial caption so a provisional translated line appears before the sentence ends; the final replaces it. |
| `PROGRESSIVE_MIN_WORDS` | integer 1–50 | `6` | Minimum words in a partial caption before it is translated progressively. |
| `PROGRESSIVE_DEBOUNCE_MS` | integer 100–5000 | `600` | Minimum time between two progressive translations of the same utterance and language. |
| `ALWAYS_ON_LANGS` | comma-separated short codes | `es` | Languages translated even when nobody is listening (so transcripts and exports exist), restricted to each stage's `targets`. |
| `LANG_GRACE_SECONDS` | number 0–600 | `10` | A language stays active this long after its last listener leaves (language demand, D8). |
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
| `BRANDING_FILE` | path | `branding.yaml` | Optional branding file (see below); when the file does not exist the neutral Lenguaraz theme is used. |
| `HOST` | address | `0.0.0.0` | Bind address of the API. |
| `PORT` | integer | `8000` | Port of the API and the audience view. |
| `LOG_LEVEL` | `DEBUG` … `ERROR` | `INFO` | Log level. Logs are JSON lines with `stage_id`, `session_id`, `seq` and `component`. |
| `WS_MAX_CONN_PER_IP` | integer ≥ 1 | `50` | Maximum simultaneous caption sockets per client IP. Raise it when many attendees share a NAT. |
| `FFMPEG_BIN` | path | `ffmpeg` | ffmpeg executable used for non-WAV files and every stream. Local 16 kHz mono WAV files never need ffmpeg. |
| `WEB_DIST` | path | *(auto)* | Folder with the built audience view. Defaults to `web/dist` next to the package (`/app/web/dist` in the container). |
| `TLS_CERT_FILE` | path | *(unset)* | PEM certificate for HTTPS served by the process itself (full chain, leaf first). Requires `TLS_KEY_FILE`: with both set, `lenguaraz serve` speaks `https://` and `wss://` on `PORT` and `/healthz` reports `"tls": true`; with neither, plain HTTP for a proxy in front. Validation: the file must exist, and one of the pair without the other stops startup with a message naming the missing key. Example: `certs/dev-cert.pem` (`make tls-selfsigned`, development only), `/app/certs/fullchain.pem` inside the container (`docs/deploy/production.md`, section 3). |
| `TLS_KEY_FILE` | path | *(unset)* | PEM private key (unencrypted) matching `TLS_CERT_FILE`. Must exist. On POSIX a key readable by group or others logs a warning at startup: keep it `chmod 600`. Never commit it (`certs/` is git-ignored). |
| `TLS_CA_FILE` | path | *(unset)* | Optional PEM CA bundle handed to uvicorn as `ssl_ca_certs` (trusted CAs; only meaningful when you verify client certificates at the app). Intermediates that browsers need belong in `TLS_CERT_FILE`, not here. Must exist when set. |
| `PROXY_HEADERS` | boolean | `true` | Honour `X-Forwarded-For` / `X-Forwarded-Proto` from the proxies listed in `FORWARDED_ALLOW_IPS`, so the per-IP socket limit and the logs see the real client instead of the proxy. `false` ignores those headers from everyone. |
| `FORWARDED_ALLOW_IPS` | comma-separated IPs / CIDRs, or `*` | `127.0.0.1,::1` | Proxies whose forwarding headers are trusted (default: a proxy on the same host). Examples: `10.0.0.5` (nginx on another host), `172.16.0.0/12` (a Docker network), `*` when port 8000 is reachable only through the proxy (the Compose `tls` profile). Headers from any other address are ignored. See `docs/security.md`. |

### Compose `tls` profile (Caddy)

`docker compose --profile tls up -d` reads two more `.env` keys that belong to
`docker-compose.yml`, not to `Settings` (the app never sees them):

- `DOMAIN` — public DNS name Caddy obtains the certificate for and serves (default
  `localhost`, which uses Caddy's internal CA; browsers warn).
- `ACME_EMAIL` — contact email registered with the Let's Encrypt account. Optional: defaults
  to `admin@<DOMAIN>` because Caddy rejects an empty `email` option.

Set `FORWARDED_ALLOW_IPS=*` with this profile (Caddy reaches the app over the Compose network
and the app port is bound to loopback only). Details: `docs/deploy/production.md`, section 3.

### `.env` profiles

Ready-made starting points under `examples/env/`; copy one to `.env` and fill the secrets:

| Profile | Use it for | What it sets |
|---|---|---|
| `examples/env/dry-run.env` | Trying the UI with no credentials | `ENGINE=fake` and a placeholder `ADMIN_TOKEN` |
| `examples/env/production.env` | A real event, on a project with billing linked **and a positive prepay balance** | `ENGINE=gemini`, model ids, hybrid VAD, progressive translation, `ALWAYS_ON_LANGS` for the overlay, a higher `WS_MAX_CONN_PER_IP` |
| `examples/env/free-tier.env` | Rehearsals, demos and recording on a project **without** a billing account (15 text requests per minute) | `ENGINE=gemini`, `PROGRESSIVE_TRANSLATION=false`, `ALWAYS_ON_LANGS` empty, `AUTO_GLOSSARY=false`, `TRANSLATE_CONTEXT_SEGMENTS=1`; watch one stage and one language at a time |

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
| `id` | string | required | Stage identifier used in URLs (`/live/{id}`, `/overlay/{id}`, `/ws/{id}`). Must be unique. |
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

## `branding.yaml`

Optional. Gives the audience pages the event's identity without touching code
(`examples/branding.example.yaml`). Served as `GET /api/branding`; the pages read it on load.

| Field | Type | Default | Validation |
|---|---|---|---|
| `event_name` | string ≤120 | `Lenguaraz` | Angle brackets are neutralized (plain text only). Shown in the header and page titles. |
| `tagline` | string ≤120 | `Live captions and translation` | Plain text. Header subtitle. |
| `primary_color` | `#RRGGBB` | `#2563eb` | Must be a 6-digit hex color. Accent for links, badges and the language picker. |
| `logo_url` | URL or path | none | `https://…`, `http://…` or `/branding/<file>` (files under the git-ignored `branding/local/` directory are served at `/branding/`). |
| `footer` | string ≤120 | `Powered by Lenguaraz · open source under Apache-2.0` | Plain text. |

Unknown fields are rejected at startup so typos are caught. Trademarks and logos are never
committed to this repository (Constitution Art. XVII.C); mount them at runtime.
