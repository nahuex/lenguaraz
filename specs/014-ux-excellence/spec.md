# Spec 014 — UX excellence & UI languages (EN/ES/PT)

**Status:** Approved · **Owner:** human · **Author:** agent · **Created:** 2026-09-25T02:30Z
**Constitution:** v1.0.1 · **Backlog row:** added by the owner on 2026-09-25T02:25Z ("la mejor página posible, mejores prácticas de UX/UI, soporte EN/ES/PT para la comunidad, creatividad con calidad sin complejizar")

## 1. Why
The pages are functional and accessible; now they must feel like a product an attendee trusts
in a dark auditorium and an operator trusts under pressure. The community around the project
speaks Spanish and Portuguese as much as English, so the interface (not only the captions)
must speak those languages. Everything stays configuration and static assets: no backend
change, no new service.

## 2. User stories
- **US-1 (P0)** As an attendee on a phone, I open the link, see immediately which stage and
  language I am reading, read comfortably at arm's length in the dark, and never lose my place
  when new lines arrive (jump-to-live when I scroll up).
- **US-2 (P0)** As an attendee whose browser is in Spanish or Portuguese, I see the interface
  in my language, and can switch it.
- **US-3 (P0)** As an attendee, when something is wrong (stage not found, captions ended,
  server unreachable, reconnecting), I understand what is happening and what to do.
- **US-4 (P1)** As an operator, the dashboard reads at a glance (state colors, what needs
  attention first), and sign-in / start / stop / export never surprise me.
- **US-5 (P1)** As an organizer, when I share the link on a chat it shows a proper title,
  description and image; attendees can add the page to their home screen.

## 3. Functional requirements
| ID | Requirement | Traces to |
|---|---|---|
| FR-014-01 | **Design brief first:** a written research note (`docs/design/brief.md`) comparing at least five market products (e.g. Wordly, Interprefy, Zoom/Meet/Teams live captions, YouTube Live subtitles, Ava, Otter) on: caption typography and line handling, language switching, connection/error states, dark/light strategy, and what to adopt or avoid; then a palette (primary/accent/semantic state colors with WCAG AA/AAA ratios listed), a type scale, and the component inventory used. No screenshots or assets copied from those products. | Art. I.2 prior art, US-1 |
| FR-014-02 | **UI languages:** every interface string in EN, ES (Rioplatense-neutral, "vos" avoided in UI copy: use neutral imperative) and PT-BR, in one dictionary module (`web/src/i18n/*.ts`, typed keys, no runtime library); language auto-detected from `navigator.languages`, switchable in the header, persisted per viewer; `<html lang>` updated; dates/numbers via `Intl`. Caption content is never translated by the UI (it comes from the backend). | US-2 |
| FR-014-03 | **Live captions page:** stage name + language always visible; captions area with a comfortable measure (≤ ~70 characters per line), large default size, high line-height, newest line emphasised, older lines dimmed; when the user scrolls up, auto-scroll pauses and a "Jump to live" button appears; interim text visually distinct but not distracting; connection state as a small pill; status/error copy as designed in the brief; keyboard shortcuts documented (`+`/`-` size, `d` theme, `l` language) with an accessible hint. | US-1, US-3 |
| FR-014-04 | **States everywhere:** loading skeletons, empty state (no stages), stage not found (with a link back), backend unreachable (retrying with countdown), stage `STOPPED` (captions ended; transcript export hint for operators), `DEGRADED` (reduced quality), rate-limited "original" marker explained on hover/focus; Admin: sign-in error, action errors, per-row state color + icon, "needs attention" ordering. | US-3, US-4 |
| FR-014-05 | **Identity & sharing:** an original SVG mark and wordmark for Lenguaraz (no third-party logos), favicon set, `theme-color`, Open Graph/Twitter meta (title, description, a generated static `og.png` ≤ 100 kB made by us), a `manifest.webmanifest` (name, icons, display standalone, colors) so phones can add the page to the home screen — no service worker (no offline promises). Branding from `branding.yaml` still overrides name/tagline/color/logo. | US-5 |
| FR-014-06 | **Quality gates:** vitest-axe on every page state; contrast ratios documented in the brief; bundle main chunk ≤ 300 kB gzip; Lighthouse-style checklist run manually by the owner at H-UI; no new backend endpoint. | NFR |

## 4. Non-functional requirements
| ID | Requirement | Measure |
|---|---|---|
| NFR-014-01 | Simplicity | No new runtime dependency beyond the design-system set; i18n is a hand-written dictionary |
| NFR-014-02 | Performance on phones | First caption visible ≤ 2 s after load on a mid-range phone (measured with the dev tools throttling at H-UI) |

## 5. Acceptance criteria (executable)
- **AC-1** `docs/design/brief.md` exists with the comparison table, palette with contrast ratios, type scale — verified by `make docs-check` (added to the required set)
- **AC-2** Switching the browser language to `pt-BR` or `es` renders the Home and Live captions pages in that language; the switcher persists — verified by vitest (i18n hook + Layout/LiveCaptions tests)
- **AC-3** Scrolling up pauses auto-scroll and shows "Jump to live"; clicking resumes — verified by a CaptionView test
- **AC-4** Each state in FR-014-04 renders its copy — verified by tests with mocked fetch/WS
- **AC-5** Axe: no violations on Home, Live captions (live, stopped, not found), Admin (signed out, signed in) — verified by `web/src/test/a11y.test.tsx`
- **AC-6** Owner checkpoint **H-UI** on the branch: approves or lists changes — human verdict

## 6. Out of scope
Translating the documentation into Portuguese; a service worker/offline mode; theming editor UI.

## 7. Open questions
- [x] Q1 Default UI language? → browser language, fallback English.
- [x] Q2 Keep the dark default? → yes (auditoriums); light and high-contrast remain one tap away.

## Changelog
- 2026-09-25T02:30Z created; Status Approved (owner request, defaults applied).
