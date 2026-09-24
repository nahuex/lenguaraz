# Tasks 006 — auto-glossary

**Plan:** specs/006-auto-glossary/plan.md

| ID | Task | Refs | Verify | Status |
|---|---|---|---|---|
| T-006-01 | `glossary/auto.py` (heuristic, merge, fake + Gemini structured-output engines), settings, `engines.py`; tests | FR-006-01/02/03, AC-1..3 | `uv run pytest tests/test_auto_glossary.py` | ☑ |
| T-006-02 | Runner integration (merged glossary for session + fan-out, snapshot fields, timeout), docs (configuration, customization); test | FR-006-01/03/04, AC-4 | `uv run pytest tests/test_runner.py && make docs-check` | ☑ |
| T-006-03 [H quota] | Quality evidence: `smoke-stt` with and without glossary on the EN sample → `docs/metrics.md` | NFR-006-02, AC-5 | `docs/metrics.md` | ☐ |
| T-006-04 | Converge; STATE.md | Art. III.3 | `make verify` | ☐ |

## Definition of Done
- [ ] All tasks ☑ · `make verify` green · docs updated · SPDX headers · STATE.md updated
