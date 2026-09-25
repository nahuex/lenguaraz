# Tasks 013 — HTTPS / TLS

**Plan:** specs/013-https-tls/plan.md

| ID | Task | Refs | Verify | Status |
|---|---|---|---|---|
| T-013-01 | Settings + validation, `build_uvicorn_kwargs`, `serve` wiring, `/healthz` `tls`; `scripts/selfsigned_cert.py` + `make tls-selfsigned`; tests (in-process HTTPS + WSS, config errors) | FR-013-01/02/04, AC-1/2 | `uv run pytest tests/test_tls.py` | ☐ |
| T-013-02 | Compose `tls` profile with Caddy + `deploy/Caddyfile`; loopback-only host port; hardening test | FR-013-03, AC-3 | `docker compose --profile tls config` + pytest | ☐ |
| T-013-03 | Web `wss://` derivation check; docs (production HTTPS, security, configuration, troubleshooting, quickstart note); CHANGELOG | FR-013-05, AC-4 | `make docs-check` | ☐ |
| T-013-04 | Converge; STATE.md | Art. III.3 | `make verify` | ☐ |

## Definition of Done
- [ ] All tasks ☑ · `make verify` + `make docs-check` green · CI green · STATE.md updated
