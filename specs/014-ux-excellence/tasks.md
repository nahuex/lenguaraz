# Tasks 014 — UX excellence & UI languages

**Plan:** specs/014-ux-excellence/plan.md · **Branch:** `feat/design-system`

| ID | Task | Refs | Verify | Status |
|---|---|---|---|---|
| T-014-01 | Research + design brief (`docs/design/brief.md`: market comparison, palette with contrast ratios, type scale, component inventory, state copy in EN/ES/PT) | FR-014-01, AC-1 | `make docs-check` | ☐ |
| T-014-02 | i18n module (EN/ES/PT), locale detection + switcher + persistence, `<html lang>`; Layout/Home/NotFound on i18n; identity assets (SVG mark, favicon, manifest, OG meta) | FR-014-02/05, AC-2 | `npm test -- --run` | ☐ |
| T-014-03 | Live captions page: layout per brief, jump-to-live, interim styling, connection pill, states, shortcuts; CaptionView tests | FR-014-03/04, AC-3/4 | `npm test -- --run` | ☐ |
| T-014-04 | Admin: state colors/icons, needs-attention ordering, error states, i18n | FR-014-04 | `npm test -- --run` | ☐ |
| T-014-05 | UX critic review → fixes; axe suite on every state; bundle budget; docs (customization: UI languages, identity), CHANGELOG | FR-014-06, AC-5 | `make verify` | ☐ |
| T-014-06 | PR; **H-UI** owner check; merge before the code freeze | AC-6 | human verdict | ☐ |

## Definition of Done
- [ ] All tasks ☑ · CI green on the PR · H-UI OK · merged before 25 13:00Z
