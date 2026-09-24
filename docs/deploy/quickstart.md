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
with a **DRY-RUN** badge. Click **Open Fogón** on a stage: captions appear within a few
seconds, word by word, from the bundled samples. `http://localhost:8000/healthz` returns
`{"status":"ok","engine":"fake","stages":2,…}`.

The dry run replays the reference transcripts that sit next to the sample audio files
(`samples/*.txt`) at speaking pace; it exercises the whole pipeline except the Gemini call.

## 2. Real transcription with Gemini

1. Create an API key in [Google AI Studio](https://aistudio.google.com/) on a project with
   **billing enabled** (the free tier limits concurrent Live sessions and daily requests, and
   may use content to improve Google products; see `docs/privacy.md`). Operators must be 18+.
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

Restart the container (`docker compose restart`). Share `http://<your-host>:8000/fogon/main`
with the audience. Anything ffmpeg can read works as a `source`; `docs/deploy/audio-sources.md`
(feature 008) has copy-paste recipes for OBS, vMix, HLS and SRT.

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
| Stage shows `STOPPED` with `authentication failed` | Wrong `GEMINI_API_KEY` → paste the key from AI Studio into `.env`. |
| Captions stop after ~10 minutes | The Live session lifetime; Lenguaraz reopens the session automatically (`ROTATING`); seamless make-before-break rotation lands in feature 003. |
| Home page says "audience view is not built yet" | Run `make web` (developer path); the Docker image builds it automatically. |
