# Spec 013 — HTTPS / TLS

**Status:** Approved · **Owner:** human · **Author:** agent · **Created:** 2026-09-25T02:30Z
**Constitution:** v1.0.1 · **Backlog row:** added by the owner on 2026-09-25T02:25Z ("listo para recibir certificado TLS y operar con HTTPS")

## 1. Why
Audience phones on a venue Wi-Fi and browsers in general expect HTTPS: mixed-content rules
block `ws://` from an `https://` page, OBS and vMix embed `https` sources, and operators
send the admin token over the network. Today HTTPS depends on the operator adding a proxy by
hand. Lenguaraz MUST be able to terminate TLS itself with a certificate the conference already
has, or obtain one automatically with one Compose profile. Moves **Deployment** and
**Security**.

## 2. User stories
- **US-1 (P0)** As an operator with a certificate from my IT department, I want to point
  Lenguaraz at the cert and key files and get `https://` and `wss://` with no extra software.
- **US-2 (P0)** As an operator with a public DNS name and no certificate, I want one command
  that obtains and renews a Let's Encrypt certificate.
- **US-3 (P1)** As a developer, I want a self-signed certificate in one command to test the
  HTTPS path locally.
- **US-4 (P0)** As a security reviewer, I want the per-IP limits and logs to see the real
  client address behind the proxy, and HSTS on public deployments.

## 3. Functional requirements
| ID | Requirement | Traces to |
|---|---|---|
| FR-013-01 | Settings `TLS_CERT_FILE` and `TLS_KEY_FILE` (both or none; validated at startup: files exist and are readable; the key file must not be world-readable on POSIX — warning only). When set, `lenguaraz serve` (uvicorn) serves HTTPS and WSS on `PORT`; `/healthz` reports `"tls": true`. Optional `TLS_CA_FILE` for a chain. | US-1 |
| FR-013-02 | Settings `PROXY_HEADERS` (default `true`) and `FORWARDED_ALLOW_IPS` (default `127.0.0.1,::1`) passed to uvicorn so `X-Forwarded-For` / `X-Forwarded-Proto` from a trusted proxy set the client address used by the per-IP WebSocket limiter and the logs. | US-4 |
| FR-013-03 | Compose profile `tls`: a Caddy service (official image, Apache-2.0, separate container) in front of Lenguaraz with automatic Let's Encrypt for `DOMAIN` (`ACME_EMAIL`), HTTP→HTTPS redirect, WebSocket upgrade on `/ws/`, HSTS (`max-age=31536000`), gzip, and Lenguaraz no longer published on 8000 to the host when the profile is active. `docker compose --profile tls up -d` is the whole command; the Caddyfile lives in `deploy/Caddyfile`. | US-2 |
| FR-013-04 | `make tls-selfsigned` writes `certs/dev-cert.pem` and `certs/dev-key.pem` (git-ignored) for `localhost` and `127.0.0.1` using the `cryptography` package (already a dependency) — no OpenSSL binary needed. | US-3 |
| FR-013-05 | The web client derives `ws://` vs `wss://` from `location.protocol` (verify; fix if hardcoded). Documentation: `docs/deploy/production.md` "HTTPS" section (both paths), `docs/security.md` (HSTS, proxy trust, key file permissions), `docs/configuration.md` (new keys), `docs/troubleshooting.md` (mixed content, cert errors, ACME failures). | Art. XVII.D |

## 4. Non-functional requirements
| ID | Requirement | Measure |
|---|---|---|
| NFR-013-01 | No new Python dependency | `cryptography` and `uvicorn[standard]` already present |
| NFR-013-02 | Container stays non-root/read-only | certs mounted read-only; Caddy has its own data volume |

## 5. Acceptance criteria (executable)
- **AC-1** With `make tls-selfsigned` and `TLS_CERT_FILE`/`TLS_KEY_FILE` set, `curl -k https://127.0.0.1:8443/healthz` returns `"tls": true` and a `wss://` client receives captions in dry-run — verified by `pytest tests/test_tls.py` (uvicorn started in-process on a free port with the generated cert; `httpx`/`websockets` clients with `verify=False`)
- **AC-2** Missing key with a cert set → startup fails with a clear `ConfigError` — verified by `pytest tests/test_tls.py`
- **AC-3** `docker compose --profile tls config` renders the Caddy service with the Caddyfile mounted and Lenguaraz without a host port — verified by `pytest tests/test_container_hardening.py::test_tls_profile`
- **AC-4** `make docs-check` green with the new keys documented — verified by `make docs-check`

## 6. Out of scope
mTLS, client certificates, certificate rotation without restart (uvicorn reload on cert change).

## 7. Open questions
- [x] Q1 Proxy choice for the profile? → Caddy (automatic ACME, one file). Nginx snippet stays in `docs/security.md` for people who already run nginx.

## Changelog
- 2026-09-25T02:30Z created; Status Approved (owner request, defaults applied).
