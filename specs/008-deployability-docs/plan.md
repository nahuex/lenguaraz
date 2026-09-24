# Plan 008 — deployability docs & submission

**Spec:** specs/008-deployability-docs/spec.md (Approved) · **Created:** 2026-09-24T22:16Z

## 1. Constitution check
| Article | Status | Note |
|---|---|---|
| I–III | ✅ | Backlog #008; tasks trace to FR-008-xx |
| IV | ✅ | No new Gemini surface |
| VIII | ✅ | Branding values are sanitized (color must match `#RRGGBB`, URLs http(s) only); logo is a URL or a path under `branding/local/` served read-only |
| XI | ✅ | `/api/branding` documented in architecture |
| XII | ✅ | Branding tests with a temp YAML; docs-check test |
| XVII.C | ✅ | No brand asset committed; `branding/local/` git-ignored |
| XVII.D | ✅ | This feature completes the set; `docs-check` enforces presence |

## 2. Verified references
| Surface | Verified via | Note |
|---|---|---|
| Cloud Run flags (`--timeout`, `--no-cpu-throttling`, `--concurrency`, `--session-affinity`, Secret Manager `--set-secrets`) | prior-art PA-1 L6 + gcloud reference (public docs) | `docs/deploy/cloud-run.md` |
| ffmpeg input recipes (file `-re`, HLS/RTMP/SRT URLs, `dshow`/`avfoundation`/`pulse` devices) | ffmpeg documentation (public) | `docs/deploy/audio-sources.md` |

## 3. Design
- `scripts/docs_check.py`: add `REQUIRED_DOCS` (FR-008-01) and README section headings (FR-008-04); keep link and config-key checks.
- `scripts/fresh_clone_test.py`: `git clone --depth 1 <repo> <tmp>`; write `.env` with `ENGINE=fake`, `ADMIN_TOKEN=<random>`; if `docker compose` works: `up --build -d`, poll `/healthz` (≤ 5 min), sleep 12 s, `GET /api/admin/stages/<first>/export?format=txt` with the token, assert non-empty, `down -v`; else: `uv sync`, `npm ci && npm run build` in `web/`, start `uv run lenguaraz serve`, same checks, terminate. `make fresh-clone-test REPO=<url>` defaults to the origin URL.
- Branding: `lenguaraz/branding.py` (`Branding` pydantic model with validators, `load_branding(path)`), setting `BRANDING_FILE`, route `GET /api/branding` in `api/app.py`, `web/src/lib/useBranding.ts` + Layout header (name, logo, accent via CSS variable).
- Docs: written per the Art. XVII.D.3 table; Spanish mirrors of README and quickstart.
- Submission: `docs/devpost.md`, `docs/video-script.md`, SRT procedure (Mangrullo → export SRT for `en` on the demo stage).

## 4. Dependencies
None new.

## 5. Risks
| Risk | Mitigation |
|---|---|
| Fresh-clone test needs the public repo to be up to date | It runs after push; CI job optional (Docker-in-runner takes minutes) |
| Docs drift after 008 | docs-check enforces presence and config keys; CHANGELOG per tag |

## 6. Verification
`make verify`, `make docs-check`, `make fresh-clone-test`, owner H3b reads the quickstart.
