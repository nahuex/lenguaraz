# Quickstart — laptop to live captions in 15 minutes

You need Docker (or Python 3.12 + uv + Node 24 for the developer path). A Gemini API key is
only needed for real transcription; the **dry run** works without any credentials.

## 1. Dry run (no credentials, 3 commands)

```bash
git clone https://github.com/nahuex/lenguaraz.git && cd lenguaraz
cp .env.example .env            # then set ENGINE=fake in .env for the dry run
docker compose up --build
```

Open http://localhost:8000. You should see two stages ("Main Stage" and "Workshop Room")
with a **DRY-RUN** badge. Click **Open live captions** on a stage: captions appear within a few
seconds, word by word, from the bundled samples. `http://localhost:8000/healthz` returns
`{"status":"ok","engine":"fake","stages":2,…}`.

The dry run replays the reference transcripts that sit next to the sample audio files
(`samples/*.txt`) at speaking pace; it exercises the whole pipeline except the Gemini call.

## 2. Real transcription with Gemini

1. Create an API key in [Google AI Studio](https://aistudio.google.com/) on a project with
   **billing enabled** (the free tier limits concurrent Live sessions and daily requests, and
   may use content to improve Google products; see `docs/privacy.md`). Operators must be 18+.
   New AI Studio billing accounts are on the **prepay** plan: buy at least USD 5 of credits
   (AI Studio → Billing → **Buy credits**) or every call answers `402 prepayment credits are
   depleted`, even with billing linked.
2. Put it in `.env`: `GEMINI_API_KEY=…` and `ENGINE=gemini`.
3. `docker compose up --build` again. The badge disappears and the captions now come from
   `gemini-3.5-transcribe-live` listening to the sample audio.

Check quality and latency from the command line (uses a little quota):

```bash
make smoke-stt      # transcribes samples/en_kubernetes.wav, prints WER, latency percentiles, tokens
```

## 3. Your own stages

Edit `stages.yaml` (every field is described in `docs/configuration.md`):

```yaml
stages:
  - id: main
    name: "Main Stage"
    source: "srt://10.0.0.5:9000?mode=caller"   # or an HLS URL, rtmp://, a file…
    source_lang: ["en-US"]
    targets: ["es"]
    glossary: ["Kubernetes", "eBPF", "YourProductName"]
```

Restart the container (`docker compose restart`). Anything ffmpeg can read works as a
`source`; `docs/deploy/audio-sources.md` has copy-paste recipes for OBS, vMix, HLS and SRT.

To share it with the audience, put HTTPS in front: the Compose stack listens on
`127.0.0.1:8000` only, and `docker compose --profile tls up -d` (with `DOMAIN` and
`ACME_EMAIL` in `.env`) gets a Let's Encrypt certificate, or use your own with
`TLS_CERT_FILE`/`TLS_KEY_FILE` — both paths in `docs/deploy/production.md`, section 3
(HTTPS). For a plain-HTTP demo on a LAN, publish the port with a `docker-compose.override.yml`
(`ports: !override ["8000:8000"]`) and share `http://<your-host>:8000/live/main`. For Google
Cloud, `docs/deploy/cloud-run.md`.

## Developer path (without Docker)

```bash
uv sync                          # Python 3.12 environment (uv installs Python if needed)
make web                         # build the audience view (needs Node 24)
ENGINE=fake make dev             # http://127.0.0.1:8000 with auto-reload
make verify                      # lint, types, tests, frontend build, SPDX headers
```

`ffmpeg` on the PATH (or `FFMPEG_BIN=/path/to/ffmpeg`) is needed for anything that is not a
16 kHz mono WAV file.

## Troubleshooting

| Symptom | Cause → fix |
|---|---|
| Stage shows `STOPPED` with `cannot open WAV` / `ffmpeg exited` | The `source` path or URL is wrong, or ffmpeg is missing → fix the path, install ffmpeg or set `FFMPEG_BIN`. |
| Stage shows `DEGRADED` with `quota exhausted (429…)` | Free-tier limits or the 10-minute spend cap → enable billing on the project, or reduce concurrent stages. |
| Captions show an `original` marker / stage detail says `rate limited (429)` | The Gemini project is on the **free tier** for the text model (`generate_content_free_tier_requests`, 15 requests/min): translations pause for the time the server asks and the original text is shown meanwhile → link a Cloud Billing account to the AI Studio project (Tier 1) and buy prepay credits; to stay on the free tier, start from `examples/env/free-tier.env` and watch one stage and one language at a time. |
| Every stage `STOPPED`/`DEGRADED` with `402 … prepayment credits are depleted` | The billing account is on the prepay plan with USD 0 → buy credits (minimum USD 5) at https://aistudio.google.com/billing; once a prepay balance exists, Cloud credits are consumed first. Alternative: unlink the project → free tier. |
| Stage shows `STOPPED` with `authentication failed` | Wrong `GEMINI_API_KEY` → paste the key from AI Studio into `.env`. |
| Stage shows `ROTATING` for a moment every ~9 minutes | Normal: the Live session lifetime is 10 minutes; Lenguaraz opens the next session before that and switches at a pause (no sentence is lost). |
| Captions stop while the speaker talks | The stall watchdog reopens the session after `STT_STALL_SECONDS`; if it repeats, check the audio level (`docs/troubleshooting.md`). |
| Home page says "audience view is not built yet" | Run `make web` (developer path); the Docker image builds it automatically. |
