# Spec 007 — hardening & CI

**Status:** Approved · **Owner:** human · **Author:** agent · **Created:** 2026-09-24T22:05Z
**Constitution:** v1.0.0 · **Backlog row:** product.md §6 #007

## 1. Why
A conference deploys what it can trust. The judges' Deployment criterion and the constitution
(Art. XVII.B, C) require a build that proves, on every push, that the code is linted, tested,
free of secrets, free of known vulnerabilities, license-clean and reproducible. Moves
**Deployment** and protects the Apache-2.0 promise.

## 2. User stories
- **US-1 (P0)** As a maintainer, I want every push to run lint, types, tests, the web build,
  a secrets scan, a vulnerability scan and the license gate, so that a red build is visible
  before anyone deploys.
- **US-2 (P0)** As a conference's legal reviewer, I want a generated list of third-party
  licenses and a gate that fails on copyleft, so that adoption needs no manual audit.
- **US-3 (P1)** As an operator, I want a documented way to report vulnerabilities and a
  container that runs non-root with a read-only filesystem, so that the service can live on a
  shared host.

## 3. Functional requirements
| ID | Requirement | Traces to |
|---|---|---|
| FR-007-01 | `make license-check` MUST list every Python (runtime) and frontend (production) dependency license, fail on any license outside the constitution allowlist (Art. XVII.B.1) and write `THIRD_PARTY_LICENSES.md` from the same data; never hand-edited. | US-2 |
| FR-007-02 | A GitHub Actions workflow MUST run on push and pull request: ruff, mypy, pytest, web lint/tests/build, `make spdx-check`, `make docs-check`, `make license-check`, gitleaks (full history), Trivy filesystem scan (HIGH/CRITICAL fail), Docker image build + Trivy image scan, Syft SBOM (SPDX JSON) uploaded as an artifact. Tests MUST run with `ENGINE=fake` and no secrets. | US-1 |
| FR-007-03 | `SECURITY.md` MUST document supported versions, how to report a vulnerability privately, the threat model summary (key server-side, admin Bearer, no persisted audio) and the hardening in place. | US-3 |
| FR-007-04 | The container MUST run as a non-root user with a read-only root filesystem and a healthcheck against `/healthz` (Dockerfile `HEALTHCHECK`, inherited by compose); documented in `docs/deploy/production.md` (008) and verified by a test that reads the Dockerfile/compose. | US-3 |
| FR-007-05 | A stall watchdog: when audio with speech keeps flowing but no transcription (interim or final) arrives for `STT_STALL_SECONDS` (default 20), the managed session MUST log, count `stalls` and reopen the session (same path as a dead session). | Metrics note D-006-2 |

## 4. Non-functional requirements
| ID | Requirement | Measure |
|---|---|---|
| NFR-007-01 | CI wall time | ≤ 10 min per run |
| NFR-007-02 | No network access to Gemini from CI | `ENGINE=fake`, no `GEMINI_API_KEY` secret configured |

## 5. Acceptance criteria (executable)
- **AC-1** `make license-check` exits 0 on the current tree, prints the inventory and regenerates `THIRD_PARTY_LICENSES.md`; with an injected forbidden license it exits 1 — verified by `pytest tests/test_license_check.py` (unit on the checker) and `make license-check`
- **AC-2** `.github/workflows/ci.yml` contains the jobs of FR-007-02 — verified by `pytest tests/test_ci_workflow.py` (parses the YAML) and by the first green run on GitHub
- **AC-3** `SECURITY.md` exists with the FR-007-03 sections — verified by `make docs-check`
- **AC-4** Dockerfile has `USER` non-root, compose has `read_only: true` and a healthcheck — verified by `pytest tests/test_container_hardening.py`
- **AC-5** With a scripted session that sends nothing for longer than the stall timeout while speech chunks flow, the managed session reopens once and `stats.stalls == 1` — verified by `pytest tests/test_session.py -k stall`

## 6. Out of scope
Signed images, SLSA provenance, dependency update bots (Dependabot config is a one-file nice-to-have if time allows).

## 7. Open questions
- [x] Q1 Fail CI on Trivy HIGH as well as CRITICAL? → yes for the fs scan; the image scan reports but does not fail on OS packages without a fix (`--ignore-unfixed`).

## Changelog
- 2026-09-24T22:05Z created; Status Approved (defaults applied).
- 2026-09-24T22:12Z FR-007-04: the healthcheck lives in the Dockerfile (compose inherits it); endpoint is `/healthz`.
