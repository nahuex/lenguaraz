# Plan 012 — design system (shadcn/ui)

**Spec:** specs/012-design-system/spec.md (Approved) · **Created:** 2026-09-24T23:05Z

## 1. Constitution check
| Article | Status | Note |
|---|---|---|
| I–III | ✅ | Owner-added backlog item; tasks trace to FR-012-xx |
| IV | ✅ | No Gemini surface |
| VIII | ✅ | Frontend only; no new data flows |
| XII | ✅ | vitest + Testing Library + vitest-axe; no network |
| XIII | ✅ | Primitives replace bespoke markup; net less CSS |
| XVII.B | ✅ | New deps all on the allowlist (table below); copied code is MIT with attribution kept |
| XVII.D | ✅ | Theming docs |

## 2. Verified references
| Surface | Verified via | Note |
|---|---|---|
| `npx shadcn@latest init` / `add <component>` on Vite + Tailwind v4 | shadcn docs (ui.shadcn.com/docs/installation/vite, /docs/tailwind-v4) | generates `components.json`, `src/lib/utils.ts`, CSS variables in `index.css` |
| Radix primitives used by the copied components | package.json after `add` | `@radix-ui/react-*` |

## 3. Design
- Branch `feat/design-system` from `main` after the naming rename.
- **Tokens:** shadcn variables (`--background`, `--foreground`, `--card`, `--primary`, `--muted`, `--border`, `--ring`, `--radius`) defined in `index.css` with the **dark palette on `:root`** (dark is the default today) and the light palette on `:root[data-theme="light"]`; the `dark:` variant is `@custom-variant dark (&:is(:root:not([data-theme='light']) *, :root[data-contrast='high'] *))`; `:root[data-contrast="high"]` overrides with black/white/yellow AAA pairs; `--caption-size` stays; the old `--accent` becomes `--accent-legacy` (utilities `bg-/text-/border-accent-legacy`, `text-accent-legacy-ink`) because shadcn owns `--accent`; `useBranding` sets `--primary`, `--ring` and a luminance-picked black/white `--primary-foreground` from `primary_color` unless high contrast is on (and removes them when it is switched on).
- **Primitives:** `web/src/components/ui/{button,card,badge,radio-group,toggle-group,switch,table,input,label,alert,skeleton,separator}.tsx` via the CLI; each file gets the SPDX line and the attribution comment on top.
- **Pages:** Home (Card per stage, Badge for state, Button links), LiveCaptions (Card header with stage + connection Badge, RadioGroup languages, ToggleGroup sizes, Switch toggles, Alert for status), Admin (Input/Label/Button sign-in, Table, Badge, Button start/stop/export), NotFound (Alert + Button). Overlay untouched except imports.
- **Tests:** existing tests adapted to the new roles (Radix RadioGroup renders `role="radio"`, Switch `role="switch"`, ToggleGroup `role="radio"` items in single mode); axe checks added with `vitest-axe`.
- **Docs & license:** NOTICE line; customization "Theming"; CONTRIBUTING note; CHANGELOG.

## 4. Dependencies (all allowlisted)
| Package | License | Purpose |
|---|---|---|
| shadcn (CLI, dev) | MIT | copies components; also ships `shadcn/tailwind.css` (the `data-checked`/`data-open`… variants the primitives use), imported by `index.css` at build time. Dev-only on purpose: as a runtime dependency it drags the CLI's tree (caniuse-lite CC-BY-4.0, minimatch/isexe BlueOak) into the production inventory and fails `make license-check` |
| radix-ui (runtime) | MIT | accessible primitives — the unified package the v4 CLI installs instead of `@radix-ui/react-*` |
| class-variance-authority | Apache-2.0 | variants |
| cn (runtime) | MIT | class merging (`cn`); the v4 CLI's replacement for clsx + tailwind-merge (`src/lib/utils.ts` re-exports it) |
| lucide-react | ISC | icons |
| tw-animate-css (dev) | MIT | animations |
| @types/node (dev) | MIT | types for `node:path` / `import.meta.dirname` in `vite.config.ts` (the `@` alias) |
| vitest-axe (dev) | MIT | a11y assertions |

Not taken: `@fontsource-variable/geist`, which the `nova` preset adds — the pages keep the system font stack (no webfont download, no third-party request from the audience page).

## 5. Risks
| Risk | Mitigation |
|---|---|
| Tailwind 4 + shadcn CLI generates `@import` lines that differ from our `@theme` setup | Init on a clean branch; reconcile `index.css` by hand; keep the old tokens as aliases until every page is migrated |
| Tests coupled to markup | Assert on roles and names, not classes |
| Time before the code freeze (25 13:00Z) | Branch; if unfinished, the branch stays open and main keeps the current UI |

## 6. Verification
`npm test -- --run`, `npm run build` (size), `make license-check`, `make verify`, owner H-UI on the branch.
