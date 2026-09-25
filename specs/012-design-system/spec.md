# Spec 012 — design system (shadcn/ui)

**Status:** Approved · **Owner:** human · **Author:** agent · **Created:** 2026-09-24T23:05Z
**Constitution:** v1.0.1 · **Backlog row:** added by the owner on 2026-09-24T22:55Z ("adoptar shadcn/ui como design system y librería de componentes")

## 1. Why
The pages work and are accessible, but they are hand-rolled Tailwind with no shared
primitives, so every new control re-invents focus rings, states and spacing. A design system
gives the audience and operator pages a consistent, polished look that judges and other
conferences recognise, and gives contributors a component vocabulary. Moves **UX** and
**Deployment** (a conference can re-theme with tokens instead of CSS surgery).

## 2. User stories
- **US-1 (P0)** As an attendee, I want the live captions page to look and behave like a
  polished product on any phone, with visible focus and clear controls.
- **US-2 (P0)** As an operator, I want the dashboard to use familiar controls (table, sign-in
  field, buttons, badges) so that nothing needs explaining on event day.
- **US-3 (P1)** As a conference, I want to re-theme the pages with a handful of tokens.
- **US-4 (P0, constraint)** As the maintainer, I want everything under Apache-2.0-compatible
  licenses with attribution kept.

## 3. Functional requirements
| ID | Requirement | Traces to |
|---|---|---|
| FR-012-01 | shadcn/ui MUST be initialised in `web/` (`components.json`, `lib/utils.ts` with `cn`, base CSS variables) on Tailwind 4 + React 19, with the existing behaviours mapped onto its tokens: light/dark (`data-theme`), high contrast (`data-contrast="high"` overriding foreground/background/primary to AAA pairs), caption size scale (`--caption-size` S–XL) and the brand color from `/api/branding` mapped to `--primary`. | US-1, US-3 |
| FR-012-02 | The UI MUST be rebuilt on shadcn primitives copied into `web/src/components/ui/`: Button, Card, Badge, RadioGroup (language picker), ToggleGroup (font size), Switch (dark mode, high contrast, show original), Table (admin), Input + Label (admin token), Alert (status and errors), Skeleton (loading), Separator. Icons from `lucide-react`. The Overlay page keeps its transparent custom CSS (it is rendered inside OBS). | US-1, US-2 |
| FR-012-03 | Accessibility MUST be preserved or improved: keyboard operation for every control, visible focus ring, the captions live region unchanged (`role="region"`, `aria-live="polite"`), radio/toggle groups with accessible names, AA contrast in default themes and AAA in high contrast; an automated axe pass (`vitest-axe`, MIT) on Home, Live captions and Admin MUST report no violations. | Art. on accessibility, US-1 |
| FR-012-04 | Licensing: copied component files carry the SPDX header plus an attribution comment ("Derived from shadcn/ui, MIT © shadcn"); `NOTICE` gets the attribution line; `make license-check` stays green (radix-ui MIT, class-variance-authority Apache-2.0, clsx MIT, tailwind-merge MIT, lucide-react ISC, tw-animate-css MIT, vitest-axe MIT). | US-4, Art. XVII |
| FR-012-05 | Docs: `docs/customization.md` gets a "Theming" section (tokens, where to change them, how branding maps to `--primary`), `CONTRIBUTING.md` a "UI components" note (use the `ui/` primitives, add with `npx shadcn add`), `CHANGELOG.md` an entry. | Art. XVII.D |

## 4. Non-functional requirements
| ID | Requirement | Measure |
|---|---|---|
| NFR-012-01 | Bundle size after the migration | ≤ 250 kB gzip for the main chunk (`npm run build` output) |
| NFR-012-02 | No backend change | Python tests untouched and green |
| NFR-012-03 | Done on a branch, merged after the owner's visual check | `feat/design-system` → PR → H-UI |

## 5. Acceptance criteria (executable)
- **AC-1** `npm test -- --run` green with the migrated tests and the axe checks — verified in CI (web job)
- **AC-2** `npm run build` green and the main chunk ≤ 250 kB gzip — verified by the build output
- **AC-3** `make license-check` green and `NOTICE` carries the shadcn attribution — verified by `make license-check` + `grep shadcn NOTICE`
- **AC-4** Owner checkpoint **H-UI**: opens `/`, `/live/main`, `/admin` on the branch with `make dev` and approves the look (or lists changes) — human verdict

## 6. Out of scope
Redesigning the information architecture; the Overlay visuals; a Storybook.

## 7. Open questions
- [x] Q1 Style preset? → shadcn default ("new-york"), neutral base color, radius 0.5 rem; brand color from branding.
- [x] Q2 Dark mode strategy? → keep `data-theme` attribute switching (already persisted per viewer); map to shadcn's `.dark`-style variables via `[data-theme="dark"]` selectors.

## Changelog
- 2026-09-24T23:05Z created; Status Approved (owner asked for shadcn/ui; defaults applied).
