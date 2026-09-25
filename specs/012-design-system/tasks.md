# Tasks 012 — design system (shadcn/ui)

**Plan:** specs/012-design-system/plan.md · **Branch:** `feat/design-system`

| ID | Task | Refs | Verify | Status |
|---|---|---|---|---|
| T-012-01 | Branch; `npx shadcn@latest init` on Vite + Tailwind 4; reconcile `index.css` tokens with `data-theme` / `data-contrast` / `--caption-size`; `useBranding` → `--primary`; SPDX + attribution on generated files; NOTICE line; `make license-check` | FR-012-01/04 | `npm run build && make license-check` | ☐ |
| T-012-02 | Add primitives (button, card, badge, radio-group, toggle-group, switch, table, input, label, alert, skeleton, separator) + lucide icons | FR-012-02 | `npm run build` | ☐ |
| T-012-03 | Migrate Home, LiveCaptions (LanguagePicker, A11yControls, CaptionView shell), Admin, NotFound; Overlay untouched | FR-012-02/03 | `npm test -- --run` | ☐ |
| T-012-04 | Tests on roles/names; `vitest-axe` checks on Home, Live captions, Admin | FR-012-03, AC-1 | `npm test -- --run` | ☐ |
| T-012-05 | Docs (customization Theming, CONTRIBUTING UI note, CHANGELOG); bundle size check; PR; **H-UI** owner check | FR-012-05, AC-2/4 | `make verify`, PR green | ☐ |

## Definition of Done
- [ ] All tasks ☑ · CI green on the PR · owner H-UI OK · merged to main before the code freeze (or the branch stays open and documented)
