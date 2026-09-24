# Troubleshooting

Symptom → cause → fix. Every stage state and detail is visible on the home page, in
`GET /api/stages` and in the JSON logs (`stage_id`, `component`).

| Symptom | Cause | Fix |
|---|---|---|
| Stage `STOPPED`, detail `cannot open WAV …` or `ffmpeg exited …` | The `source` path or URL is wrong, or ffmpeg is missing for a non-WAV source | Check the path/URL from the machine running Lenguaraz; install ffmpeg or set `FFMPEG_BIN`; test the source with `ffmpeg -i <source> -t 5 -f null -` |
| Stage `STOPPED`, detail `authentication failed (401/403)` or `API key not valid` | Wrong or missing `GEMINI_API_KEY` | Paste the key from Google AI Studio into `.env` (never in `stages.yaml`); restart |
| Stage `DEGRADED`, detail `quota exhausted (429 …)` | Free-tier limits, the per-project concurrent Live session cap, or the Tier 1 spend cap per 10 minutes | Enable billing on the project (AI Studio → API key → project → billing); reduce concurrent stages; the stage reconnects with backoff on its own |
| Stage `DEGRADED`, detail `connect failed … retry n/5` | Network or Google-side outage | Nothing to do for a few seconds; after 5 failed reconnects the stage goes `STOPPED` with the last error, restart it once the network is back |
| Stage `ROTATING` every ~9 minutes | Normal: Live sessions last about 10 minutes and Lenguaraz reopens them proactively | Nothing; captions continue. Tune with `SESSION_ROTATE_SECONDS` |
| Captions appear but in the wrong language | Auto-detection (`source_lang: []`) picked the wrong language, or the hint is wrong | Set an explicit BCP-47 hint per stage (`source_lang: ["en-US"]`); use `[]` only for mixed-language stages |
| A technical term or a name keeps coming out wrong | It is not in the stage glossary, or the glossary exceeds 100 terms (only the first 100 are sent) | Add the term (exact spelling) to `glossary` in `stages.yaml`; keep the list under 100 prioritized terms |
| Partial captions update but finals take many seconds | Server-side turn detection waiting for a pause | Keep `VAD_MODE=hybrid` (default); lower `VAD_SILENCE_MS` for fast speakers; raise `VAD_THRESHOLD` in noisy rooms so noise is not taken as speech |
| Translated captions show the original text and a "degraded" mark, original captions keep flowing | The translation model failed three times (quota, outage) for that language; the status detail names the language | Check the detail (`translation to es failed: …`); on quota, enable billing or reduce languages; the next final retries automatically |
| A listener picks a language and sees nothing for ~10 s | The language had no listener and is not in `ALWAYS_ON_LANGS`; it becomes active with the next final caption | Expected on the first join; add the language to `ALWAYS_ON_LANGS` if it must always be ready |
| Translation is right but slow (several seconds) | `GEMINI_TRANSLATE_THINKING` set above `minimal`, or long segments | Use `minimal`; keep `PROGRESSIVE_TRANSLATION=true` so a provisional line appears while the sentence is spoken |
| WebSocket closes with `4429` | Too many caption sockets from one IP (`WS_MAX_CONN_PER_IP`) — typical behind a venue NAT | Raise `WS_MAX_CONN_PER_IP` |
| WebSocket closes with `4413` | The client could not keep up; the server never drops final captions, so it closed the socket | The client reconnects automatically; check the network of that device |
| Home page says "audience view is not built yet" | Developer path without `make web` | `make web`; the Docker image builds it automatically |
| `make smoke-stt` reports a high WER on the bundled sample | SMART mode formats numbers ("300" for "three hundred") which the reference spells out; or the audio is broken | Compare the finals by eye; regenerate samples with `make samples`; use `--mode VERBATIM` to compare |
