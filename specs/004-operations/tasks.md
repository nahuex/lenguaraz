# Tasks 004 — operations

**Plan:** specs/004-operations/plan.md · Legend: `[P]` parallelizable · `[H]` needs human · each task ≤ 45 min.

| ID | Task | Refs | Verify | Status |
|---|---|---|---|---|
| T-004-01 | Acta: `lenguaraz/export.py` store + SRT/VTT/TXT renderers, tests with golden strings; runner feeds the store from the bus | FR-004-01, FR-004-02, AC-1, AC-2, NFR-004-01 | `uv run pytest tests/test_export.py` | ☐ |
| T-004-02 | `lenguaraz/pricing.py` + snapshot fields (`running`, `audio_seconds`, `est_cost_usd`, `transcript_entries`) | FR-004-03 | `uv run pytest tests/test_runner.py` | ☐ |
| T-004-03 | Mangrullo API `lenguaraz/api/admin.py`: Bearer dependency, list, start/stop, export; tests | FR-004-02, FR-004-03, AC-3, AC-4, AC-5 | `uv run pytest tests/test_admin.py` | ☐ |
| T-004-04 [P] | Frontend: Mangrullo page, Pizarrón overlay, api helpers, links from Home/StageCard, vitest suites (background agent) | FR-004-04, FR-004-05, AC-6 | `cd web && npm test && npm run build` | ☐ |
| T-004-05 | Docs: runbook (event-day checklist, export after the talk), architecture, customization (overlay params), troubleshooting (401, empty export); `make docs-check` | FR-004-06, AC-7 | `make docs-check` | ☐ |
| T-004-06 | Converge: spec vs code, Shipped, STATE.md, README "What it does today" | Art. III.3 | `make verify` | ☐ |

## Estimate vs clock
Started 21:27Z; M4 deadline 25 03:00Z (5.5 h) shared with 005 and 006. Budget for 004: 75 min.

## Definition of Done (feature)
- [ ] All tasks ☑ and all ACs pass
- [ ] `make verify` green
- [ ] Docs updated per Art. XVII.D.6
- [ ] New files carry SPDX headers
- [ ] STATE.md updated
