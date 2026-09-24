# Tasks 007 — hardening & CI

**Plan:** specs/007-hardening-ci/plan.md

| ID | Task | Refs | Verify | Status |
|---|---|---|---|---|
| T-007-01 | `scripts/license_check.py` + dev deps + `make license-check` + generated `THIRD_PARTY_LICENSES.md`; tests | FR-007-01, AC-1 | `uv run pytest tests/test_license_check.py && make license-check` | ☑ |
| T-007-02 | `.github/workflows/ci.yml` (python, web, gitleaks, trivy fs, image + trivy + SBOM), `.github/dependabot.yml`; test parses the workflow | FR-007-02, AC-2 | `uv run pytest tests/test_ci_workflow.py` + first green run | ☑ |
| T-007-03 | `SECURITY.md`; container hardening test (non-root, read-only, healthcheck) | FR-007-03/04, AC-3/4 | `uv run pytest tests/test_container_hardening.py && make docs-check` | ☑ |
| T-007-04 | Stall watchdog in `ManagedSttSession` (`STT_STALL_SECONDS`), snapshot `stalls`, docs (configuration, troubleshooting, runbook) | FR-007-05, AC-5 | `uv run pytest tests/test_stt_session.py -k stall` | ☑ |
| T-007-05 | Converge; STATE.md; check the CI run on GitHub | Art. III.3 | `gh run list --limit 1` green | ☐ |

## Definition of Done
- [ ] All tasks ☑ · `make verify` green · CI green on main · docs updated · SPDX headers · STATE.md updated
