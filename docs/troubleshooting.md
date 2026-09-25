# Troubleshooting

Symptom → cause → fix. Every stage state and detail is visible on the home page, in
`GET /api/stages` and in the JSON logs (`stage_id`, `component`).

| Symptom | Cause | Fix |
|---|---|---|
| Stage `STOPPED`, detail `cannot open WAV …` or `ffmpeg exited …` | The `source` path or URL is wrong, or ffmpeg is missing for a non-WAV source | Check the path/URL from the machine running Lenguaraz; install ffmpeg or set `FFMPEG_BIN`; test the source with `ffmpeg -i <source> -t 5 -f null -` |
| Stage `STOPPED`, detail `authentication failed (401/403)` or `API key not valid` | Wrong or missing `GEMINI_API_KEY` | Paste the key from Google AI Studio into `.env` (never in `stages.yaml`); restart |
| Stage `DEGRADED`, detail `quota exhausted (429 …)` | Free-tier limits, the per-project concurrent Live session cap, or the Tier 1 spend cap per 10 minutes | Enable billing on the project (AI Studio → API key → project → billing); reduce concurrent stages; the stage reconnects with backoff on its own |
| Stage `DEGRADED`, detail `connect failed … retry n/5` | Network or Google-side outage | Nothing to do for a few seconds; after 5 failed reconnects the stage goes `STOPPED` with the last error, restart it once the network is back |
| Stage `ROTATING` every ~9 minutes | Normal: Live sessions last about 10 minutes; Lenguaraz opens the next one while the current one still listens (make-before-break) | Nothing; captions continue and `last_rotation_gap_ms` in `/api/stages` shows the measured gap. Tune with `SESSION_ROTATE_SECONDS` |
| `ROTATING` with detail `next session failed … retry n/5` | The next Live session could not be opened (quota, concurrent-session cap: a rotation briefly needs two sessions per stage) | The current session keeps transcribing; the attempt retries with backoff; if all fail the stage returns to `LIVE` with `rotation postponed` and tries again at the next timer or `GoAway`. Plan quota for N stages + 1 |
| A sentence appears twice around a rotation | Both sessions finalized the same words | Should not happen: the dedupe window drops identical finals within `DEDUPE_WINDOW_SECONDS`; raise it slightly if the speaker repeats sentences verbatim |
| `chunks_dropped` grows in `/api/stages` for a stream | Audio arrived while no session was connected (start or reconnect) and the 5 s backlog overflowed | Expected during reconnects; if it grows continuously the machine cannot keep up (CPU) or the network to Google is stalled |
| Captions appear but in the wrong language | Auto-detection (`source_lang: []`) picked the wrong language, or the hint is wrong | Set an explicit BCP-47 hint per stage (`source_lang: ["en-US"]`); use `[]` only for mixed-language stages |
| A technical term or a name keeps coming out wrong | It is not in the stage glossary, or the glossary exceeds 100 terms (only the first 100 are sent) | Add the term (exact spelling) to `glossary` in `stages.yaml`; keep the list under 100 prioritized terms |
| Partial captions update but finals take many seconds | Server-side turn detection waiting for a pause | Keep `VAD_MODE=hybrid` (default); lower `VAD_SILENCE_MS` for fast speakers; raise `VAD_THRESHOLD` in noisy rooms so noise is not taken as speech |
| Translated captions show the original text and a "degraded" mark, original captions keep flowing | The translation model failed three times (quota, outage) for that language; the status detail names the language | Check the detail (`translation to es failed: …`); on quota, enable billing or reduce languages; the next final retries automatically |
| A listener picks a language and sees nothing for ~10 s | The language had no listener and is not in `ALWAYS_ON_LANGS`; it becomes active with the next final caption | Expected on the first join; add the language to `ALWAYS_ON_LANGS` if it must always be ready |
| Translation is right but slow (several seconds) | `GEMINI_TRANSLATE_THINKING` set above `minimal`, or long segments | Use `minimal`; keep `PROGRESSIVE_TRANSLATION=true` so a provisional line appears while the sentence is spoken |
| WebSocket closes with `4429` | Too many caption sockets from one IP (`WS_MAX_CONN_PER_IP`) — typical behind a venue NAT | Raise `WS_MAX_CONN_PER_IP` |
| Captions show an `original` marker / stage detail says `rate limited (429)` | The Gemini project is on the **free tier** for the text model (`generate_content_free_tier_requests`, 15 requests/min): translations pause for the time the server asks and the original text is shown meanwhile | Link a Cloud Billing account to the AI Studio project (Tier 1) **and buy prepay credits** (next row). To stay on the free tier, start from `examples/env/free-tier.env` (final-only translation, no always-on language, no auto-glossary) and watch one stage and one language at a time |
| Every stage `DEGRADED` or `STOPPED` at once with detail `402 RESOURCE_EXHAUSTED: Your prepayment credits are depleted`; translated captions show the original text; `make smoke-stt` fails the same way | The project is Tier 1 on a Cloud Billing account with the **prepay** plan and a **USD 0** balance: every call, Live transcription and text alike, is refused until credits are bought. Linking billing alone is not enough | Buy prepay credits (minimum USD 5) at https://aistudio.google.com/billing → **Buy credits**; once a prepay balance exists, eligible Google Cloud credits are consumed first. Calls resume within a minute or two: press `Start` on stopped stages. Alternative: unlink the project from the billing account → back to the free tier with `examples/env/free-tier.env`. Details in the section below |
| WebSocket closes with `4413` | The client could not keep up; the server never drops final captions, so it closed the socket | The client reconnects automatically; check the network of that device |
| `/api/admin/*` answers `401` | Missing or wrong `Authorization: Bearer <ADMIN_TOKEN>` header | Copy the token from `.env`; the Admin page keeps it in session storage only |
| Export answers `404` with `available: [...]` | That stage produced no final caption in the requested language yet (language not active or no listener) | Pick a listed language, or add it to `ALWAYS_ON_LANGS` so it is always produced |
| Home page says "audience view is not built yet" | Developer path without `make web` | `make web`; the Docker image builds it automatically |
| `make smoke-stt` reports a high WER on the bundled sample | SMART mode formats numbers ("300" for "three hundred") which the reference spells out; or the audio is broken | Compare the finals by eye; regenerate samples with `make samples`; use `--mode VERBATIM` to compare |
| The page loads over `https://` but captions never connect; the browser console says `Mixed Content` … `attempted to connect to the insecure WebSocket endpoint ws://` | The page is HTTPS but its WebSocket reaches Lenguaraz over plain HTTP: a proxy that terminates TLS without forwarding the `/ws/` upgrade, or a stale cached page | The client picks `wss://` whenever the page is `https://`, so fix the proxy (`docs/security.md`: `Upgrade`/`Connection` headers on `/ws/`) or use the Compose `tls` profile, which handles the upgrade; then hard-reload the page |
| Browser warns "Your connection is not private"; `curl` fails with `self-signed certificate` but works with `-k` | A `make tls-selfsigned` certificate, or the Let's Encrypt **staging** CA left enabled in `deploy/Caddyfile` | Expected in development: accept the warning or use `curl -k`. For an event use a real certificate (`TLS_CERT_FILE` with the full chain, leaf first, or Android phones reject it) or Caddy with the production CA (comment out `acme_ca`) |
| Caddy logs `could not get certificate from issuer`, `connection refused`, `NXDOMAIN` or `rateLimited`; the site answers `ERR_SSL_PROTOCOL_ERROR` | The ACME challenge failed: TCP 80/443 not reachable from the internet, `DOMAIN` not resolving to this host yet, or too many issuance attempts | Open 80 and 443 in the firewall/cloud rules; `dig +short $DOMAIN` must print this host's public address; once DNS is right, `docker compose --profile tls restart caddy`; rehearse with the staging CA (`acme_ca` in `deploy/Caddyfile`) to stay under Let's Encrypt limits |
| `lenguaraz serve` exits with `TLS_KEY_FILE is not set`, `TLS_CERT_FILE not found` or `Permission denied` on the key | One of the pair is missing, the path is wrong (inside the container it is `/app/certs/…`), or the key is not readable by uid 10001 | Set both files or neither; in Docker mount `./certs:/app/certs:ro` and `sudo chown 10001 certs/privkey.pem`; keep the key `chmod 600` |

## Captions stop while the speaker keeps talking

The Live API occasionally goes quiet without closing the session (seen once in ~15 runs
during development). The stall watchdog handles it: when audio above `VAD_THRESHOLD` keeps
flowing but no interim or final arrives for `STT_STALL_SECONDS` (default 20), the stage
logs `stall`, closes the session and opens a new one; the stage snapshot in the Admin page counts
it under `stalls`. If you see stalls every few minutes, check the audio level first (a stream
that is too quiet never triggers speech and never captions), then raise `STT_STALL_SECONDS`
for very slow speakers or set it to `0` to disable the watchdog.

## 402: prepayment credits are depleted

**Symptom:** every stage goes `DEGRADED` or `STOPPED` at the same moment with detail
`402 RESOURCE_EXHAUSTED: Your prepayment credits are depleted. Please go to AI Studio at
https://ai.studio/projects`; translated captions show the original text; `make smoke-stt`
fails with the same message. Nothing is wrong with the key or the network.

**Cause:** the AI Studio project is linked to a Cloud Billing account on the **prepay** plan
(the default for new accounts) and the prepay balance is **USD 0**. Linking the account moves
the project to Tier 1, but on the prepay plan every request is refused until credits are
bought — even when the billing account holds Google Cloud promotional credits, because those
are consumed only once an active prepay balance exists.

**Fix:** open https://aistudio.google.com/billing, check that the right billing account is
selected, press **Buy credits** and buy the minimum (USD 5). Calls succeed again within a
minute or two; press `Start` on the stopped stages (or restart the container) and confirm with
`make smoke-stt` → `RESULT: PASS`. With a prepay balance in place, eligible Cloud credits are
consumed first, so the USD 5 stay almost untouched.

**Alternative:** unlink the project from the billing account (Cloud console → Billing →
Account management) and it returns to the free tier: 15 text requests per minute and a
handful of concurrent Live sessions. Run it from `examples/env/free-tier.env` and watch one
stage and one language at a time. Not for a real event: the free tier may use content to
improve Google products (`docs/privacy.md`).
