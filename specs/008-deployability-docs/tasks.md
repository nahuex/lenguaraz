# Tasks 008 — deployability docs & submission

**Plan:** specs/008-deployability-docs/plan.md

| ID | Task | Refs | Verify | Status |
|---|---|---|---|---|
| T-008-01 | `docs/deploy/production.md`, `docs/deploy/audio-sources.md`, `docs/deploy/cloud-run.md`; quickstart refresh (no "feature NNN" leftovers) | FR-008-01/06 | `make docs-check` | ☑ |
| T-008-02 | `docs/security.md`, `docs/privacy.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md` | FR-008-01 | `make docs-check` | ☑ |
| T-008-03 | Branding runtime config (`BRANDING_FILE`, `/api/branding`, header), `examples/branding.example.yaml`, `examples/stages.multitrack.yaml`, `examples/env/*.env`; docs (configuration, customization); tests | FR-008-03, AC-3 | `uv run pytest tests/test_branding.py && make verify` | ☑ |
| T-008-04 | `scripts/docs_check.py` required set + README sections; `scripts/fresh_clone_test.py` + `make fresh-clone-test`; test | FR-008-01/02, AC-1/2 | `uv run pytest tests/test_docs_check.py && make fresh-clone-test` | ☑ (fresh-clone PASS 22:25Z, Docker, 42 s) |
| T-008-05 | README EN: docs index, badge, Prior art & acknowledgments, How we built it, limitations, screenshot placeholder; `README.es.md`; `docs/es/quickstart.md` | FR-008-04, AC-4 | `make docs-check` | ☑ (screenshot placeholder for H4) |
| T-008-06 | `docs/devpost.md`, `docs/video-script.md` (+ SRT export procedure) | FR-008-05, AC-5 | `make docs-check` | ☑ |
| T-008-07 | Converge; STATE.md; H3b request; tag `v0.2.0` after H3 | Art. III.3 | `make verify && make fresh-clone-test` | ☑ (CI run 36067758346 green; `v0.2.0` waits for H3) |

## Definition of Done
- [x] All tasks ☑ · `make verify` + `make docs-check` + `make fresh-clone-test` green · CI green · STATE.md updated
