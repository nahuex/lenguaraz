# Security policy

## Supported versions

| Version | Supported |
|---|---|
| `main` and the latest tag | yes |
| older tags | no |

## Reporting a vulnerability

Please do **not** open a public issue for security problems. Use GitHub's private
vulnerability reporting on this repository ("Security" tab → "Report a vulnerability"), or
email the maintainer listed in `NOTICE`. Include the version or commit, steps to reproduce
and the impact you see. You will get an acknowledgement within 72 hours and a fix or a
mitigation plan as soon as the issue is confirmed; we publish an advisory with credit unless
you prefer otherwise.

## Threat model in short

- **The Gemini API key lives only on the server** (`GEMINI_API_KEY` environment variable).
  It never reaches a browser, a log line, a commit or a test fixture. Audience pages talk to
  Lenguaraz only over WebSocket; the browser never talks to Google.
- **Operator actions need a Bearer token** (`ADMIN_TOKEN`, compared in constant time). Without
  it the admin API (`/api/admin/*`) and the Admin page refuse every request.
- **Audio is never stored.** PCM frames flow from ffmpeg to the transcription session and are
  discarded; only text captions are kept in memory for the transcript export and are
  gone when the process stops.
- **Prompt injection through the microphone** is a real vector: whatever a speaker says is
  transcribed and then translated. Transcripts, glossary terms and talk metadata enter the
  translation prompt as delimited data with an explicit "data, not instructions" rule, angle
  brackets are neutralized, and outputs are length-capped and sanitized before display.
- **Per-IP WebSocket limits** (`WS_MAX_CONN_PER_IP`) and bounded queues protect the process
  from slow or abusive clients; a slow consumer is disconnected, never the whole stage.
- **Age and terms:** the Gemini API requires users to be 18+; the deployment must comply with
  Google's terms and the Prohibited Use Policy.

## Hardening in place

- Container runs as a non-root user with a read-only root filesystem, `no-new-privileges`,
  `tmpfs` for `/tmp`, and a healthcheck on `/healthz` (`Dockerfile`, `docker-compose.yml`).
- CI (`.github/workflows/ci.yml`) runs on every push: ruff, mypy, tests, frontend build,
  SPDX and docs checks, `make license-check`, **gitleaks** over the full history, **Trivy**
  filesystem and image scans, and a **Syft SBOM** (SPDX JSON) published as a build artifact.
- A pre-commit hook (`make hooks`) runs gitleaks and the SPDX check locally.
- Tests never call the real API (`ENGINE=fake`); CI has no Gemini secret configured.
- Dependencies are limited to the licenses allowed by the project constitution
  (`THIRD_PARTY_LICENSES.md`), and Dependabot proposes updates weekly.

See `docs/security.md` for deployment guidance (reverse proxy, TLS, token rotation) and
`docs/privacy.md` for what is and is not retained.
