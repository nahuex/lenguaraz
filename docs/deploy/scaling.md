# Scaling — from 2 to 30+ stages

## What a stage costs the machine

Every stage is one isolated pipeline in the same process: an ffmpeg process (or the built-in
WAV reader), one Live transcription session, an in-memory bus and one translation worker per
active language. Measured with `make simulate` on 2026-09-24 (`docs/scale-report.md`):

| Setup | CPU (process, % of one core) | RSS | Notes |
|---|---|---|---|
| 10 stages (2 real Gemini + 8 simulated), 60 s | 10.3 % avg, 31.7 % peak | 67 → 85 MB | Windows laptop, 12 CPUs; the simulated stages replay audio and captions without the model |
| + per real stage | ≈ 2–5 % of a core for ffmpeg decoding when the source is not raw PCM | ≈ a few MB | The Live session itself is I/O bound |

Rule of thumb: **one modern 2-vCPU VM runs 10 stages comfortably; 30 stages fit in 4 vCPU
and 1 GB of RAM** — the API quota is the real limit, not the machine.

## Adding stages

Add entries to `stages.yaml` and restart (`docker compose up -d --build`, or `Start` in
Mangrullo after a restart). Nothing else changes: the audience picks the stage on the home
page, the overlay URL follows the stage id, exports are per stage.

## API quota planning

- **Concurrent Live sessions per project** (Google AI Studio → your project's limits): you
  need `stages + 1` because a rotation briefly overlaps two sessions per stage.
- **Spend cap per rolling 10 minutes** (Tier 1 USD 10, Tier 2 USD 50, Tier 3 USD 200): 30
  stages ≈ USD 0.30 per minute → USD 3 per 10 minutes, within Tier 1.
- Translation requests scale with finals × active languages (≈ 1 request every 4–6 s per
  stage per language); `ALWAYS_ON_LANGS` decides what is translated with nobody listening.
- The free tier caps concurrent Live sessions at a handful and requests per day per model:
  use a paid-tier project.

## Audience fan-out

Captions are small JSON messages over WebSocket (≈ 200 bytes each, a few per second per
stage). One process serves thousands of sockets; beyond that, put several Lenguaraz replicas
behind any HTTP load balancer with sticky sessions per stage, or an HLS/CDN caption track for
very large audiences (the OBS overlay burns captions into the video for the stream itself).

## Beyond one machine (roadmap)

The bus is an interface (`lenguaraz/bus/base.py`). A Redis pub/sub implementation with a
per-stage lock lets several workers share the stages (`--scale worker=N`); it was designed
(product.md D6/D8, prior art PA-1 L5) but cut from the hackathon build to protect the core.
Until then: one process per machine, stages partitioned by `stages.yaml` files.

## Report

The full per-stage table, the method and the honesty note about real versus simulated stages
are in [`docs/scale-report.md`](../scale-report.md); regenerate with
`make simulate SIM_ARGS="--stages 30 --seconds 120 --real 4"`.
