# Tasks NNN — <feature-name>

**Plan:** specs/NNN-<feature>/plan.md · Legend: `[P]` parallelizable · `[H]` needs human · each task ≤ 45 min.

| ID | Task | Refs | Verify | Status |
|---|---|---|---|---|
| T-NNN-01 | Write failing test for … | FR-NNN-01, AC-1 | `pytest -k …` | ☐ |
| T-NNN-02 | Implement … | FR-NNN-01 | `make verify` | ☐ |
| T-NNN-03 [H] | Human checkpoint: … | AC-… | human confirms | ☐ |

## Definition of Done (feature)
- [ ] All tasks ☑ and all ACs pass
- [ ] `make verify` green
- [ ] Docs updated per Art. XVII.D.6 (configuration / architecture / troubleshooting / runbook as applicable)
- [ ] New files carry SPDX headers; `make license-check` green
- [ ] STATE.md updated, commit tagged if milestone
