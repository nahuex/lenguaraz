# Plan 014 — UX excellence & UI languages

**Spec:** specs/014-ux-excellence/spec.md (Approved) · **Created:** 2026-09-25T02:30Z · **Branch:** `feat/design-system` (after spec 012 lands on it)

## 1. Constitution check
| Article | Status | Note |
|---|---|---|
| I.2 Prior art | ✅ | Research note cites products for lessons; nothing copied |
| VIII | ✅ | No new data flows; OG image is static |
| XII | ✅ | vitest + axe; no network |
| XIII Simplicity | ✅ | Hand-written i18n; no new runtime libs |
| XVII.C | ✅ | Original mark; no third-party logos |
| XVII.D | ✅ | brief + customization docs |

## 2. Design
- **Workflow shape:** (1) research agent (web reading, read-only) → `docs/design/brief.md`; (2) three implementation agents with disjoint scopes: i18n infrastructure + Layout/Home/NotFound + identity assets; LiveCaptions + CaptionView (jump-to-live, states, shortcuts); Admin (states, ordering, errors); (3) UX critic agent (read-only) scores against the brief and the spec, listing concrete fixes; (4) fixer agent applies the accepted fixes and runs every gate.
- **i18n:** `web/src/i18n/{index.ts,en.ts,es.ts,pt.ts}`: `type Key = keyof typeof en`, `useT()` returns `(key, vars?) => string`, `useLocale()` with `setLocale`; detection from `navigator.languages` matching `es*`, `pt*`, else `en`; persisted in `localStorage` (`lenguaraz.locale`); `<html lang>` updated; the header switcher is a RadioGroup-like segmented control with accessible names.
- **Captions UX:** CaptionView gets `atBottom` tracking (scroll listener + `IntersectionObserver` sentinel), a floating "Jump to live" Button when not at bottom, `prefers-reduced-motion` respected; typography tokens: `--caption-size` scale unchanged, `max-width: 38rem`, `line-height: 1.35`.
- **Identity:** `web/public/{favicon.svg,icon-192.png,icon-512.png,og.png,manifest.webmanifest}`; mark: a simple speech-bubble with two overlapping horizontal bars (two languages) in the brand color, drawn as SVG by us; PNGs rendered from the SVG with a script in Python (`cairosvg` is not available → use `Pillow` only if present; otherwise author PNGs via a small script using `resvg`? Not available → generate PNGs with Node `sharp`? Avoid deps: ship the SVG favicon + a hand-authored 512 PNG drawn with Pillow if present in the venv, else document the manual step). Keep the `og.png` simple text-on-color rendered with Pillow.
- **Meta:** `index.html` gets title/description/OG/Twitter/theme-color/manifest; branding still overrides at runtime for the header.

## 3. Dependencies
None new at runtime. Pillow (dev, MIT-CMU/HPND — allowlist check: the HPND license is OSI-approved and permissive; add "HPND" to the allowlist in `scripts/license_check.py` with a note) only if used to render PNGs.

## 4. Risks
| Risk | Mitigation |
|---|---|
| Two workflows touching `web/src` | 014 starts only after 012's gate finishes and is committed |
| Creativity vs. rules | The brief lists what the judges' criteria value (quality, latency visibility, accessibility); no feature outside the MVP scope, only presentation |
| Bundle growth | Budget 300 kB gzip; check in the gate |

## 5. Verification
`npm test -- --run`, `npm run build`, axe suite, `make verify`, `make docs-check`, owner H-UI.
