# Production — one VM with Docker Compose

Target: a single virtual machine (2 vCPU, 4 GB RAM is plenty for up to ~10 stages; see
`docs/deploy/scaling.md`), Docker with the Compose plugin, a DNS name, and a Gemini API key
on a **paid-tier** Google AI Studio project. Time: about an hour, most of it DNS and TLS.

## 1. Host

```bash
# Ubuntu 24.04 example
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
sudo usermod -aG docker "$USER" && newgrp docker
git clone https://github.com/nahuex/lenguaraz.git && cd lenguaraz
```

Open inbound TCP 80/443 (reverse proxy) and the UDP ports of your SRT stages (see
`docs/deploy/audio-sources.md`). Port 8000 stays private to the host.

## 2. Configuration

```bash
cp examples/env/production.env .env
```

Edit `.env` (every key is documented in `docs/configuration.md`):

| Key | Set to |
|---|---|
| `ENGINE` | `gemini` |
| `GEMINI_API_KEY` | your key (never commit `.env`) |
| `ADMIN_TOKEN` | a long random string: `openssl rand -hex 32` |
| `SESSION_ROTATE_SECONDS` | keep `540` (the Live API session limit is 10 minutes) |
| `ALWAYS_ON_LANGS` | languages that must be translated even with no listener (e.g. `es` for the overlay) |
| `WS_MAX_CONN_PER_IP` | raise it (e.g. `200`) when the venue Wi-Fi NATs everyone behind one address |
| `LOG_LEVEL` | `INFO` (`DEBUG` is verbose but never logs audio or the key) |

Then describe your event in `stages.yaml` (`examples/stages.multitrack.yaml` is a 3-track
starting point) and, optionally, your identity in `branding.yaml`
(`examples/branding.example.yaml`). Nothing about a specific conference is hardcoded.

## 3. Reverse proxy with TLS

Lenguaraz speaks plain HTTP and WebSocket on `:8000`. Put a proxy in front for TLS and
compression. Caddy does it in four lines (automatic Let's Encrypt certificates):

```caddyfile
captions.example.org {
    reverse_proxy 127.0.0.1:8000
}
```

`docs/security.md` has the equivalent nginx block (WebSocket upgrade on `/ws/`) and the
security checklist. Do not cache `/ws/` or `/api/`.

## 4. Run

```bash
docker compose up --build -d
docker compose logs -f --tail 50          # JSON logs; stage_id / session_id / seq on every line
curl -s http://127.0.0.1:8000/healthz     # {"status":"ok","engine":"gemini","stages":N,…}
```

The compose file already runs the container **non-root, read-only** (`tmpfs` on `/tmp`,
`no-new-privileges`), restarts it on failure and mounts `stages.yaml` and `samples/`
read-only. The image healthcheck polls `/healthz` every 15 s.

Open `https://captions.example.org/` (Home), `/fogon/<stage>` (audience),
`/pizarron/<stage>?lang=es&lines=2` (OBS browser source) and `/mangrullo` (operators, asks
for `ADMIN_TOKEN`).

## 5. Sizing

Measured with the built-in simulator (`docs/scale-report.md`): ten stages in one process
used about 10 % of one core on average (peaks around 30 %) and +18 MB RSS. ffmpeg decoding
adds roughly 2–5 % of a core per live stream. Budget **2 vCPU / 2 GB for up to 10 stages**,
and check your Google project's concurrent Live session limit before adding more
(`docs/deploy/scaling.md`, `docs/cost.md`).

## 6. Back up the configuration

Everything that defines your deployment is three small files: `.env` (secrets — store it in
your password manager or secret store, not in git), `stages.yaml` and `branding.yaml`
(safe to keep in a private git repo). Captions are not persisted: export transcripts from
Mangrullo (SRT/VTT/TXT) **before** stopping a stage if you want to keep them.

## 7. Upgrade

```bash
git pull
docker compose up --build -d      # rebuilds the image; ~1 min of downtime for all stages
```

Read `CHANGELOG.md` first; configuration keys are only added, never renamed, within a major
version. To roll back: `git checkout <previous tag>` and the same command.

## 8. Event day

Follow `docs/operations/runbook.md` (T-24h, T-1h, during, after) and keep
`docs/troubleshooting.md` at hand.

## Alternatives

- **Cloud Run** (no VM to manage, but stateful stages need one always-on instance):
  `docs/deploy/cloud-run.md`.
- **Without Docker:** the developer path in `docs/deploy/quickstart.md` plus a `systemd`
  unit running `uv run lenguaraz serve --host 127.0.0.1 --port 8000`.
