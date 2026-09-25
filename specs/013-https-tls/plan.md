# Plan 013 — HTTPS / TLS

**Spec:** specs/013-https-tls/spec.md (Approved) · **Created:** 2026-09-25T02:30Z

## 1. Constitution check
| Article | Status | Note |
|---|---|---|
| I–III | ✅ | Owner-added item; tasks trace to FR-013-xx |
| VIII Security | ✅ | TLS at the edge or in-process; proxy trust explicit; HSTS |
| XII Tests | ✅ | In-process uvicorn with a generated cert; no network beyond loopback |
| XVII.B | ✅ | No new Python deps; Caddy runs as a separate container (Apache-2.0) |
| XVII.D | ✅ | production/security/configuration/troubleshooting updated |

## 2. Verified references
| Surface | Verified via | Note |
|---|---|---|
| uvicorn `ssl_certfile`, `ssl_keyfile`, `ssl_ca_certs`, `proxy_headers`, `forwarded_allow_ips` | uvicorn docs / installed `uvicorn.config.Config` signature | passed from `lenguaraz serve` |
| Caddy `reverse_proxy`, automatic HTTPS, `header Strict-Transport-Security` | Caddy docs (public) | `deploy/Caddyfile` |
| `cryptography.x509` self-signed certificate builder | package docs | `scripts/selfsigned_cert.py` |

## 3. Design
- `config.py`: `tls_cert_file`, `tls_key_file`, `tls_ca_file: Path | None`, `proxy_headers: bool = True`, `forwarded_allow_ips: str = "127.0.0.1,::1"`; validator: cert and key both or none, files exist; `Settings.tls_enabled` property.
- `cli.py serve`: builds uvicorn kwargs from settings (`build_uvicorn_kwargs(settings)` pure function, unit-tested).
- `api/app.py /healthz`: add `"tls": settings.tls_enabled`.
- `scripts/selfsigned_cert.py` + `make tls-selfsigned`; `certs/` in `.gitignore`.
- `docker-compose.yml`: service `caddy` with `profiles: ["tls"]`, image `caddy:2`, ports 80/443, volumes `./deploy/Caddyfile:/etc/caddy/Caddyfile:ro`, `caddy_data`, `caddy_config`; env `DOMAIN`, `ACME_EMAIL`; Lenguaraz's host port binding moved to a base file plus an override? Simplest: keep `8000:8000` bound to `127.0.0.1` only (`"127.0.0.1:8000:8000"`) so it is never public; Caddy reaches it on the compose network. Document.
- `deploy/Caddyfile`: `{$DOMAIN} { encode gzip; header Strict-Transport-Security "max-age=31536000"; reverse_proxy lenguaraz:8000 }` (Caddy upgrades WebSockets automatically).
- Web: check `web/src/lib/*` for `ws://` construction; use `location.protocol === 'https:' ? 'wss:' : 'ws:'`.

## 4. Dependencies
None new (Caddy is an external container, not a bundled dependency).

## 5. Risks
| Risk | Mitigation |
|---|---|
| Key file permissions in the container (read-only mount, non-root user) | Document `chmod 640` + group, or mount with `:ro` and correct owner; warning at startup only |
| ACME rate limits when testing | Document Let's Encrypt staging (`acme_ca` directive) |

## 6. Verification
`pytest tests/test_tls.py`, `make verify`, `make docs-check`, `docker compose --profile tls config`.
