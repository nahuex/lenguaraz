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

Open inbound TCP 80/443 (HTTPS; add UDP 443 for HTTP/3 with the Caddy profile) and the UDP
ports of your SRT stages (see `docs/deploy/audio-sources.md`). Port 8000 is published on the
host's loopback only by `docker-compose.yml`; nothing reaches the app except through TLS.

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

## 3. HTTPS

Browsers block `ws://` captions from an `https://` page, OBS and vMix embed `https` sources,
and operators send `ADMIN_TOKEN` over the network: run HTTPS. Pick one of three paths.

### A. Your own certificate (Lenguaraz terminates TLS)

Your IT department gave you a certificate for the venue domain. Point Lenguaraz at the PEM
files and it serves `https://` and `wss://` itself, no extra software. The container runs as
uid 10001, so make the key readable by that user and by nobody else:

```bash
mkdir -p certs
cp /path/to/fullchain.pem certs/fullchain.pem     # leaf first, then intermediates
cp /path/to/privkey.pem   certs/privkey.pem       # unencrypted PEM
chmod 600 certs/privkey.pem && sudo chown 10001 certs/privkey.pem
```

Add the paths **as seen inside the container** to `.env`:

```dotenv
TLS_CERT_FILE=/app/certs/fullchain.pem
TLS_KEY_FILE=/app/certs/privkey.pem
```

Mount the folder read-only and publish 443 instead of loopback 8000 with a
`docker-compose.override.yml` (Compose merges it automatically):

```yaml
services:
  lenguaraz:
    ports: !override
      - "443:8000"
    volumes:
      - ./certs:/app/certs:ro
```

```bash
docker compose up -d
curl -s https://captions.example.org/healthz      # …,"tls":true}
```

The audience page derives `wss://` from the page address, so nothing else changes. Rules:
both files or neither (a lone key or a missing file stops startup with a message naming the
key); the certificate file holds the full chain; the image healthcheck follows the scheme.
To renew, replace the files and `docker compose restart lenguaraz`. Path A serves HTTPS only
(there is no plain-HTTP listener to redirect from): share `https://` links. Without Docker,
the same two variables with host paths and `uv run lenguaraz serve --port 8443`. For a local
test, `make tls-selfsigned` writes a self-signed pair into `certs/` (never for an event).

### B. Automatic certificate with Caddy (Let's Encrypt)

You have a public DNS name pointing at this host and no certificate. One Compose profile adds
[Caddy](https://caddyserver.com/) (official image, Apache-2.0, a separate container) in
front of Lenguaraz: it obtains and renews the certificate, redirects HTTP to HTTPS, upgrades
WebSockets, sends HSTS and compresses. `deploy/Caddyfile` is the whole configuration.

```dotenv
# .env
DOMAIN=captions.example.org
ACME_EMAIL=ops@example.org          # Let's Encrypt account contact (optional; default admin@DOMAIN)
FORWARDED_ALLOW_IPS=*               # trust Caddy's X-Forwarded-For (see below)
```

```bash
docker compose --profile tls up -d
docker compose --profile tls logs -f caddy        # wait for "certificate obtained successfully"
curl -s https://captions.example.org/healthz      # …,"tls":false}  (TLS ends at Caddy)
```

Before you start: DNS for `DOMAIN` must already resolve to this host, and inbound TCP 80
**and** 443 must be open (80 carries the ACME challenge and the redirect; UDP 443 adds
HTTP/3). `FORWARDED_ALLOW_IPS=*` is safe here because the app port is bound to loopback and
only Caddy reaches it over the Compose network; it makes the per-IP limit count attendees
instead of Caddy. Certificates live in the `caddy_data` volume and survive restarts and
upgrades. Stop everything with `docker compose --profile tls down`.

**Testing tip.** Let's Encrypt limits issuance (5 duplicate certificates per week). While
you rehearse with a real domain, uncomment the `acme_ca` line in `deploy/Caddyfile` to use
the **staging** CA (browsers warn, which is expected), then comment it out again and
`docker compose --profile tls restart caddy` for the real certificate.

### C. You already run nginx, Traefik or Caddy

Keep Lenguaraz on plain HTTP (the default `127.0.0.1:8000`), forward the `/ws/` upgrades and
tell Lenguaraz which proxy to trust so the per-IP limit and the logs see attendees, not the
proxy:

```dotenv
FORWARDED_ALLOW_IPS=127.0.0.1,::1     # proxy on the same host (the default); else its IP or CIDR
```

The nginx block (WebSocket upgrade, `X-Forwarded-*` headers) and the security checklist are
in `docs/security.md`. Do not cache `/ws/` or `/api/`.

## 4. Run

```bash
docker compose up --build -d
docker compose logs -f --tail 50          # JSON logs; stage_id / session_id / seq on every line
curl -s http://127.0.0.1:8000/healthz     # {"status":"ok","engine":"gemini","stages":N,…}
```

The compose file already runs the container **non-root, read-only** (`tmpfs` on `/tmp`,
`no-new-privileges`), restarts it on failure and mounts `stages.yaml` and `samples/`
read-only. The image healthcheck polls `/healthz` every 15 s.

Open `https://captions.example.org/` (Home), `/live/<stage>` (live captions for the audience),
`/overlay/<stage>?lang=es&lines=2` (OBS browser source) and `/admin` (operators, asks
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
the Admin page (SRT/VTT/TXT) **before** stopping a stage if you want to keep them.

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
