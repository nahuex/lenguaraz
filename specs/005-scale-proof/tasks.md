# Tasks 005 — scale-proof

**Plan:** specs/005-scale-proof/plan.md

| ID | Task | Refs | Verify | Status |
|---|---|---|---|---|
| T-005-01 | `tools/simulate.py` (mixed engines, listeners, sampler, report md+json), CLI + Makefile, `psutil` dev dep; fake-only test | FR-005-01…04, AC-1 | `uv run pytest tests/test_simulate.py` | ☑ |
| T-005-02 [H quota] | `make simulate` with `--stages 10 --seconds 60 --real 2`; commit the report; numbers into README/cost docs | FR-005-02, AC-2 | `docs/scale-report.md` | ☑ |
| T-005-03 | Docs: `docs/cost.md` (formula, measured numbers, worked example), `docs/deploy/scaling.md` (2 → 30+ stages, quota planning, capacity table, Redis path as future work); `make docs-check` | Art. XVII.D, AC-3 | `make docs-check` | ☐ |
| T-005-04 | Converge; STATE.md; **H3** review with the owner (report + cost table) | Art. III.3, H3 | human verdict | ☐ (converged; H3 verdict pending) |
| T-005-05 | Viewer fan-out load test: `tools/loadtest.py` (subprocess fake server, `websockets` viewers, spread p50/p95, psutil on the real server process), CLI `loadtest` + Makefile `loadtest`, `websockets>=13` declared, tests (pure parts + 20 viewers × 2 s), run 100/500/1000 × 30 s, docs (`docs/loadtest-report.md`, `## Viewer fan-out` in the scale report, `scaling.md`, `metrics.md`) | FR-005-05, NFR-005-03, AC-4 | `uv run pytest tests/test_loadtest.py`; `make loadtest` | ☑ |

## Definition of Done
- [ ] All tasks ☑ · `make verify` green · docs updated · SPDX headers · STATE.md updated
