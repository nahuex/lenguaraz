# Plan 007 — hardening & CI

**Spec:** specs/007-hardening-ci/spec.md (Approved) · **Created:** 2026-09-24T22:05Z

## 1. Constitution check
| Article | Status | Note |
|---|---|---|
| I–III | ✅ | Backlog #007; tasks trace to FR-007-xx |
| IV Docs-verified | ✅ | No new Gemini surface; the stall watchdog reuses the reconnect path (GT-3) |
| VI Resilience | ✅ | Stall watchdog = one more failure mode handled like a dead session |
| VIII Security | ✅ | gitleaks, Trivy, non-root, read-only, SECURITY.md |
| XII Tests | ✅ | CI runs `ENGINE=fake`; new tests parse Dockerfile/compose/workflow |
| XVII Licensing | ✅ | `pip-licenses` (MIT) and `license-checker` (BSD-3-Clause) added as dev tools; allowlist enforced |

## 2. Verified references
| Surface | Verified via | Note |
|---|---|---|
| `pip-licenses --format=json --from=mixed` | tool `--help` at install | Python inventory |
| `license-checker --production --json` | tool `--help` at install | frontend inventory |
| `gitleaks/gitleaks-action@v2`, `aquasecurity/trivy-action`, `anchore/sbom-action` | official action READMEs (GitHub) | CI actions |

## 3. Design
- `scripts/license_check.py`: runs both tools, normalizes license strings (SPDX-ish), applies the allowlist from the constitution (module constant `ALLOWED`, LGPL flagged as "needs human approval" → fail unless listed in `LICENSE_EXCEPTIONS`), writes `THIRD_PARTY_LICENSES.md` (table per ecosystem), exits 1 on violations. Pure functions (`classify`, `render`) unit-tested with fixtures.
- `.github/workflows/ci.yml`: jobs `python` (uv sync, ruff, mypy, pytest, spdx, docs, license), `web` (npm ci, lint, test, build), `secrets` (gitleaks full history), `trivy-fs`, `image` (docker build, Trivy image, Syft SBOM artifact).
- `SECURITY.md` at the root; `docs/security.md` (008) links to it.
- Stall watchdog in `ManagedSttSession`: track `last_transcript_at` and `last_speech_at` (chunk RMS ≥ threshold); the main loop's wait timeout checks `now - last_transcript_at > stall_seconds and last_speech_at > last_transcript_at` → `stats.stalls += 1`, treat as dead session (`_replace_dead_session`). Setting `STT_STALL_SECONDS` (0 disables).
- Dependabot config for pip, npm and actions (weekly).

## 4. Dependencies (dev only)
| Package | License | Purpose |
|---|---|---|
| pip-licenses | MIT | Python license inventory |
| license-checker (npm) | BSD-3-Clause | frontend license inventory |

## 5. Risks
| Risk | Mitigation |
|---|---|
| A transitive package reports an odd license string ("Apache Software License" classifier) | Normalization map; unknown → fail with the package named, so the human decides |
| Trivy image scan flags Debian packages without fixes | `--ignore-unfixed` on the image scan |
| CI can't be observed from here until pushed | Workflow YAML validated by a test; first run checked with `gh run list` |

## 6. Verification
`make verify` + `make license-check` + `gh run watch` on the first CI run.
