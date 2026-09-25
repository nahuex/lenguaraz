# Lenguaraz design brief (spec 014, FR-014-01)

**Status:** Draft for H-UI · **Author:** agent (product design) · **Date:** 2026-09-24
**Scope:** Home `/`, Live captions `/live/{stage}`, Overlay `/overlay/{stage}` (visuals unchanged), Admin `/admin`.
**Stack:** React 19 + Tailwind 4 + shadcn/ui (spec 012). No backend change, no new runtime dependency.

This brief is research first, then decisions concrete enough to implement without asking.
Nothing here is copied from the products reviewed: only lessons, each with the public page that was read.

## 1. Market research (10 products, pages read 2026-09-24)

| Product | Caption typography and line handling | Language switching | Connection / quality / error states shown to viewers | Dark / light | Join flow | ADOPT | AVOID | Source |
|---|---|---|---|---|---|---|---|---|
| Google Meet captions | Rolling captions over the video; viewer can scroll back through history; font, size, colour and background customisable; settings persist | Caption language and translation target chosen in a settings panel (~90 languages) | Only "feature rolling out" notes; no viewer-facing degraded state documented | Follows the app; text/background colour settable | Inside the meeting only | Persisted display settings; scroll-back history | Burying the language choice three menus deep | https://support.google.com/meet/answer/10964115 |
| Microsoft Teams live captions | Adjustable font size, colour, background and caption height; number of visible lines can be raised; captions can be repositioned; settings persist | Spoken language confirmed first, then a "translate to" toggle with a target list (~28 languages) | None documented beyond licensing notes; profanity masked | Follows the app theme; colour options | Inside the meeting only | Separate "spoken" vs "translate to" concepts; user-set line count | Translation gated behind a premium licence with no explanation in place | https://support.microsoft.com/en-us/office/use-live-captions-in-microsoft-teams-meetings-4be2d304-f675-4b57-8347-cbd000a21260 |
| Zoom translated captions | Captions sit above the toolbar; font size via a slider in accessibility settings; line count not documented | Caption language in a dropdown next to the caption button; translation toggled separately | No unavailability message documented; whether translation exists depends on the host's plan | Follows the client theme | Inside the meeting only | One-tap caption button with the language right beside it | Silent absence of translation when the host lacks the add-on | https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060844 |
| Wordly (in-person events) | Phone-first text stream; "word-by-word" or "full-phrase" display mode; optional white-on-black | Language picked before joining, switchable any time | Not documented; attendees are told to rejoin with the same link if disconnected | Light default, black background as an accessibility option | QR code or link, no account, no app | QR + link with zero sign-up; language chosen up-front; a phrase-level display option | Making the viewer rejoin manually after a drop; captions vanishing after the session with no export | https://www.wordly.ai/faq |
| Interprefy mobile app | Captions behind a "CC" icon; typography not documented | Audio language first; captions language follows it by default but can be changed independently | Advice to use reliable Wi-Fi; no in-app quality indicator documented | Not documented | Event token typed or QR-scanned, then Connect | Captions language following the audio choice by default | A token step before the first caption; an app install | https://knowledge.interprefy.com/interprefy-mobile-app-user-guide |
| YouTube Live auto captions | Standard player captions (viewer styles them in the player); English only for live; captions are regenerated after the stream | No viewer choice for live (single language) | Accuracy disclaimer on the help page, not in the player | Player theme | CC button in the player | An honest accuracy disclaimer | Captions that disappear when the stream ends; a single language | https://support.google.com/youtube/answer/6373554 |
| Ava | Text size slider; dark or light background; picture-in-picture floating captions | Spoken language and (paid) translation language in the conversation settings | Not documented in the settings article | User-toggled dark mode | App, one tap to start | Text size as a first-class control; PiP idea for multitasking | Gating translation behind a paid tier without saying so in the UI | https://help.ava.me/en/articles/2823128-how-to-change-the-settings-in-a-conversation |
| StreamText | Browser text stream; preset themes or custom font, size and colours; screen-reader readable | Single stream per event link | Not documented on the FAQ | Presets including night-style themes | Event link, no plugin | Presets instead of a colour picker; screen-reader friendliness | Exposing a dozen raw formatting knobs to a phone user | https://streamtext.net/faqs/ |
| Otter live captions (Zoom) | Captions rendered inside the Zoom window; no separate transcript view documented for participants | Not documented | Not documented (breakout-room limitation only) | Host app | Host enables; participants click a button | Nothing new beyond "one button to show captions" | Depending on the host client for everything the viewer sees | https://otter.ai/blog/zoom-captions |
| Verbit Venue Live | Captions on venue screens or personal devices; typography not documented | 30+ translation languages | Accuracy target stated in marketing, not shown to viewers | Not documented | QR code to a phone page, or venue screens | Big-screen plus personal-device duality (our Overlay + Live pages) | Making promises ("99%") the viewer cannot verify | https://verbit.ai/solutions-real-time/venue-live/ |

### Lessons carried into Lenguaraz
1. **Zero-friction join:** link or QR, no account, no app, no token; the stage and language are visible in the first second (Wordly, Verbit).
2. **Language is a primary control**, next to the captions, never inside a settings tree (Zoom, Meet negative lessons).
3. **Persist display settings per viewer** and offer few, meaningful presets (Meet, Teams, StreamText) rather than raw formatting knobs.
4. **Be honest about quality in place:** a visible pill for connection, a banner for degraded/ended, an explained "original" marker; no vanishing captions (YouTube, Wordly negative lessons).
5. **Dark by default in an auditorium** with light and high-contrast one tap away; no auto-flashing between themes.
6. **Never make the viewer rejoin by hand:** reconnect with backoff, show a countdown, keep the lines already read.
7. **Keep the transcript:** STOPPED shows an "ended" state and operators export SRT/VTT/TXT (nobody in the table lets the viewer see that the text survives).

## 2. What exists today (gap list for engineers)
- Tokens in `web/src/index.css` (`--surface`, `--ink`, `--accent`, `--focus`, `--caption-size` S–XL, `data-theme` / `data-contrast` / `data-font-size`).
- `StateBadge` uses amber for STARTING/ROTATING and orange for DEGRADED; the connection dot uses orange for `error`. This brief reassigns: starting/rotating = blue, degraded = amber, error = red.
- `CaptionView` shows the last N finals with no scroll-back, no jump-to-live, no newest-line emphasis; the "original" marker is a `title` tooltip only (not reachable by keyboard or touch).
- Copy is English-only and lives inside components; no favicon/OG/manifest; `theme-color` missing.
- Admin table has no attention ordering, no per-row state colour beyond the badge, errors are bare strings.

## 3. Palette

Principles: neutrals carry the page, one primary (sky) for actions, one accent (teal) for emphasis, five semantic hues that are never the only carrier of meaning (always icon + label). All ratios below were computed with the WCAG 2.1 relative-luminance formula; text pairs are graded AA ≥ 4.5:1, AAA ≥ 7:1; non-text UI pairs need ≥ 3:1.

### 3.1 Dark theme (default, `data-theme="dark"`)
| Token | Hex | Used for | Against | Ratio | Grade |
|---|---|---|---|---|---|
| `--surface` | `#0f172a` | page background | — | — | — |
| `--surface-raised` | `#1e293b` | cards, captions panel, header | — | — | — |
| `--ink` | `#f8fafc` | body text, newest caption | surface / raised | 17.06 / 13.98 | AAA |
| `--ink-muted` | `#cbd5e1` | labels, older captions | surface / raised | 12.02 / 9.85 | AAA |
| `--interim` | `#94a3b8` | interim (partial) line | surface / raised | 6.96 / 5.71 | AA |
| `--line` | `#64748b` | borders that mean something (cards, inputs, chips) | surface / raised | 3.75 / 3.07 | AA (UI) |
| `--divider` | `#334155` | decorative separators, skeletons (no meaning) | surface | 1.72 | n/a |
| `--primary` | `#38bdf8` | buttons, links, active chip, newest-line rule | surface / raised | 8.33 / 6.83 | AAA / AA |
| `--primary-foreground` | `#082f49` | text on primary | primary | 6.48 | AA |
| `--primary-hover` | `#7dd3fc` | hover/active fills | surface | 10.71 | AAA |
| `--accent` | `#2dd4bf` | mark's second bar, selected-language underline | surface | 9.59 | AAA |
| `--accent-foreground` | `#042f2e` | text on accent | accent | 7.77 | AAA |
| `--focus` | `#facc15` | 3 px focus ring | surface | 11.66 | AA (UI) |
| `--state-live` | `#4ade80` | live dot/text | surface / raised | 10.25 / 8.40 | AAA |
| `--state-busy` | `#60a5fa` | starting, rotating, connecting | surface / raised | 7.02 / 5.75 | AAA / AA |
| `--state-degraded` | `#fbbf24` | degraded, reconnecting | surface / raised | 10.69 / 8.76 | AAA |
| `--state-stopped` | `#94a3b8` | idle, stopped | surface / raised | 6.96 / 5.71 | AA |
| `--state-error` | `#f87171` | connection failed, action failed | surface / raised | 6.45 / 5.29 | AA |

Solid badges (dark): live `#22c55e` on-ink `#052e16` (6.54 AA) · busy `#60a5fa` / `#0c1a3a` (6.75 AA) · degraded `#f59e0b` / `#451a03` (6.97 AA) · stopped `#94a3b8` / `#0f172a` (6.96 AA) · error `#f87171` / `#450a0a` (5.84 AA).
"Original" marker chip: ink `#cbd5e1` on `#334155` (6.97 AA), 1 px border `#64748b` (3.07 on raised, AA UI).

### 3.2 Light theme (`data-theme="light"`)
| Token | Hex | Against | Ratio | Grade |
|---|---|---|---|---|
| `--surface` `#ffffff` · `--surface-raised` `#f1f5f9` · `--divider` `#cbd5e1` | — | — | — | — |
| `--ink` | `#0f172a` | surface / raised | 17.85 / 16.30 | AAA |
| `--ink-muted` | `#475569` | surface / raised | 7.58 / 6.92 | AAA / AA |
| `--interim` | `#475569` | surface / raised | 7.58 / 6.92 | AAA / AA |
| `--line` | `#64748b` | surface / raised | 4.76 / 4.34 | AA (UI) |
| `--primary` | `#075985` | surface | 7.56 | AAA |
| `--primary-foreground` | `#ffffff` | primary | 7.56 | AAA |
| `--primary-hover` | `#0369a1` | surface | 5.93 | AA |
| `--accent` | `#0f766e` | surface | 5.47 | AA |
| `--accent-foreground` | `#ffffff` | accent | 5.47 | AA |
| `--focus` | `#1d4ed8` | surface | 6.70 | AA (UI) |
| `--state-live` | `#15803d` | surface / raised | 5.02 / 4.58 | AA |
| `--state-busy` | `#1d4ed8` | surface / raised | 6.70 / 6.12 | AA |
| `--state-degraded` | `#b45309` | surface / raised | 5.02 / 4.58 | AA |
| `--state-stopped` | `#475569` | surface | 7.58 | AAA |
| `--state-error` | `#b91c1c` | surface / raised | 6.47 / 5.91 | AA |

Tinted badges (light): live `#dcfce7` / ink `#14532d` (8.30 AAA) · busy `#dbeafe` / `#1e3a8a` (8.49 AAA) · degraded `#fef3c7` / `#78350f` (8.15 AAA) · stopped `#e2e8f0` / `#1e293b` (11.87 AAA) · error `#fee2e2` / `#7f1d1d` (8.20 AAA). "Original" chip: `#334155` on `#e2e8f0` (8.40 AAA).

### 3.3 High contrast (`data-contrast="high"`, wins over theme, AAA everywhere)
| Token | Hex | Ratio on `#000000` | Grade |
|---|---|---|---|
| `--surface`, `--surface-raised` | `#000000` | — | — |
| `--ink`, `--ink-muted`, `--line`, `--state-stopped` | `#ffffff` | 21.00 | AAA |
| `--primary`, `--accent`, `--interim` | `#ffd54f` (ink `#000000`, 14.88) | 14.88 | AAA |
| `--focus` | `#ffff00` | 19.56 | AA (UI) |
| `--state-live` | `#00e676` | 12.58 | AAA |
| `--state-busy` | `#82b1ff` | 9.68 | AAA |
| `--state-degraded` | `#ffab40` | 11.15 | AAA |
| `--state-error` | `#ff8a80` | 9.20 | AAA |

High-contrast badges use the state colour as background with `#000000` text (same ratios). Links are always underlined; selected chips invert (white fill, black text). The brand colour is ignored in high contrast.

### 3.4 Brand colour override (`branding.yaml: primary_color`)
`useBranding` already publishes `--brand`. Rules:
1. `--primary` := `--brand` **only for fills** (buttons, active chips, header rule, newest-line rule, jump-to-live button). Link text keeps the theme primary unless `contrast(brand, surface) ≥ 4.5`.
2. `--primary-foreground` := `#000000` when the brand's relative luminance Y > 0.179, else `#ffffff`. At the threshold both give 4.58:1, so every brand colour gets ≥ 4.5:1 on its fill. Computed examples: `#e11d48` → white (4.70) · `#22d3ee` → black (11.62) · `#f97316` → black (7.49) · `#1e3a8a` → white (10.36) · example `#7c3aed` → white (5.70) · default `#2563eb` → white.
3. If `contrast(brand, surface) < 3` the header rule is drawn with `--line` instead (a brand too close to the background disappears).
4. Implementation: one pure function `foregroundFor(hex)` in `web/src/lib/color.ts` (~15 lines, unit-tested with the examples above); `useBranding` sets `--brand`, `--brand-foreground` and `--brand-on-surface-ok` (`1` / `0`).

## 4. Type, spacing, radius, elevation

**Font stack:** `system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif`. No webfont (privacy, speed, no third-party asset). Numbers in Admin use `font-variant-numeric: tabular-nums`.

| Role | Size | Line-height | Weight | Notes |
|---|---|---|---|---|
| Caption S | 1.25 rem (20 px) | 1.35 | 400 / newest 500 | phone minimum |
| Caption M (default) | 1.75 rem (28 px) | 1.35 | 400 / newest 500 | arm's length on a phone |
| Caption L | 2.5 rem (40 px) | 1.25 | 400 / newest 500 | tablet / laptop |
| Caption XL | 3.5 rem (56 px) | 1.2 | 500 | letter-spacing −0.01 em |
| Original (secondary line) | 0.6 em of caption | 1.3 | 400 | `lang` attribute set |
| "original" marker chip | 0.45 em of caption, min 0.75 rem | 1 | 600, uppercase, +0.06 em | |
| Page h1 | 1.5 rem / 1.875 rem ≥ 768 px | 1.25 | 700 | |
| Card title h2 | 1.125 rem | 1.3 | 600 | |
| Body | 1 rem | 1.5 | 400 | |
| Meta / labels | 0.875 rem | 1.5 | 500 | |
| Overline (table headers, group legends) | 0.75 rem | 1.5 | 600, uppercase, +0.06 em | |

- **Measure:** captions column `max-inline-size: min(100%, 34em)` where `em` is the caption size → ~60–70 characters at every size; centred on ≥ 768 px, full width with 16 px gutters on phones. `overflow-wrap: anywhere` stays.
- **Spacing rhythm:** 4 px base; steps 4 · 8 · 12 · 16 · 24 · 32 · 48. Gutters 16 px (phone) / 24 px (≥ 640 px); section gap 24 px; card padding 16 px; gap between caption lines 12 px (S/M) and 16 px (L/XL); chip padding 8 × 12 px, min height 44 px on touch.
- **Radius (shadcn `--radius: 0.5rem`):** buttons/inputs `md` 0.5 rem · cards and the captions panel `lg` 0.75 rem · chips, pills and badges 9999 px.
- **Elevation:** dark and high contrast use **borders only** (shadows vanish on dark). Light: cards `shadow-sm`; sticky header `shadow-sm` once scrolled; jump-to-live button `shadow-md`; dialogs/sheets `shadow-lg`. Never a shadow on caption text (that belongs to the Overlay only).
- **Focus:** 3 px `--focus` ring, 2 px offset, on every interactive element (unchanged).

### Component inventory (shadcn primitives in `web/src/components/ui/`)
| Primitive | Where | Notes |
|---|---|---|
| Button (default, secondary, outline, ghost, icon) | everywhere | primary fill = brand-aware `--primary` |
| Badge (custom `state` variant) | StateBadge on Home, Live, Admin | icon + label, `data-state` |
| Card | StageCard, sign-in card, captions panel | |
| RadioGroup | caption language (≤ 4 options) | falls back to Select when > 4 |
| ToggleGroup | font size S/M/L/XL, lines 2/3/5 | accessible names "Small … Extra large" |
| Switch | dark theme, high contrast, show original | |
| Select | UI language, export language, caption language > 4 | native `<select>` on phones is acceptable |
| DropdownMenu | UI language in the header (globe icon) | |
| Tooltip + Popover | "original" marker (hover/focus → Tooltip; tap → Popover) | |
| Alert (info, warning, destructive) | status banners, errors | |
| Skeleton | loading Home cards, Admin rows, captions panel | |
| Table | Admin | rows become cards < 768 px (existing pattern) |
| Sheet (bottom) | "Display" settings on phones | |
| Dialog | keyboard shortcuts help | |
| Separator, Kbd (tiny custom) | shortcuts dialog, footer | |
| Icons (lucide-react) | `Radio` live · `Loader` starting · `RefreshCw` rotating · `TriangleAlert` degraded · `CircleStop` stopped · `CircleX` error · `Languages` · `Type` · `Sun` / `Moon` · `Contrast` · `ArrowDownToLine` jump · `Keyboard` · `Globe` | all `aria-hidden`; the label is text |

## 5. Live captions page (`/live/{stage}`)

### 5.1 Layout, phone first (≤ 640 px)
```
┌──────────────────────────────────────────────┐
│ ‹  Stage name · Español            ● Live  ⚙ │  compact header, 48 px, sticky
├──────────────────────────────────────────────┤
│ [English (original)] [Español] [Português]   │  language chips, 44 px, horizontal scroll if needed
├──────────────────────────────────────────────┤
│ (banner only when needed: ended / degraded / │
│  reconnecting / not found)                   │
├──────────────────────────────────────────────┤
│                                              │
│   older line, muted                          │  captions panel fills the rest of 100dvh,
│   older line, muted                          │  bottom-aligned, scrollable
│ ▌ newest final, ink, weight 500              │
│   interim partial text, italic, muted        │
│                    [↓ Jump to live · 3 new]  │  floating, only when scrolled up
├──────────────────────────────────────────────┤
│ Caption delay: about 1.8 s     Shortcuts (?) │  footer meta, 0.875 rem
└──────────────────────────────────────────────┘
```
- The global brand header collapses to the compact row on `/live` (Layout variant `compact`): mark or `logo_url`, stage name + current language, connection pill, UI-language globe, "Display" gear.
- **Connection pill:** dot + label; `connecting` in `--state-busy`, `reconnecting` in `--state-degraded`, `live` in `--state-live`, `error` in `--state-error`; the dot pulses only when motion is allowed. `role="status"`, `aria-live="polite"`.
- **Tablet / desktop (≥ 768 px):** the settings live in an inline bar under the chips (no Sheet); the captions column is centred at the measure; the panel keeps ≥ 60 vh height. Nothing else moves, so the two layouts share one component tree.

### 5.2 Captions area behaviour
- Keeps the last 50 finals (existing `MAX_FINALS`); renders all of them in a scroll container; `lines` becomes "how many are shown at full opacity when pinned to live" (2/3/5), older ones stay readable above in `--ink-muted`.
- **Auto-scroll:** pinned while the viewport bottom is within 48 px of the end; new finals scroll it (smooth only when motion is allowed). If the user scrolls up, pinning pauses and a floating **Jump to live** button appears (primary fill, `ArrowDownToLine` icon, counter of unseen finals). Pressing it, pressing `End`, or scrolling back to the bottom resumes pinning. This is AC-3.
- **Newest line:** `--ink`, weight 500, 3 px left rule in `--primary` (6.83:1 on raised). Older: `--ink-muted`, weight 400, no rule. Never opacity tricks (contrast must stay measurable).
- **Interim:** always the last row, italic, `--interim`, no rule, reserved `min-height` of one line so a final replacing it never shifts the layout; not announced (`aria-live="off"`, existing).
- **"Original" marker:** a focusable chip (`<button type="button">`) after a degraded line; Tooltip on hover/focus, Popover on tap; `aria-describedby` points at the tooltip text (copy in §6). The chip never carries meaning by colour alone: its label is the word "original".
- **Show original:** second line under each final (0.6 em, muted, `lang=source_lang`); off by default.
- **Live region:** unchanged (`role="region"`, `aria-label`, `aria-live="polite"`, finals only).

### 5.3 Controls
Font size (ToggleGroup S/M/L/XL) · Lines (2/3/5) · Theme (Switch dark/light) · High contrast (Switch) · Show original (Switch) · UI language (header globe). All persisted in `localStorage` under `lenguaraz.*` (existing store) plus `lenguaraz.uiLang`. Caption language stays in the URL (`?lang=`) so a shared link opens in that language.

### 5.4 Keyboard shortcuts (ignored while focus is in an input, select or textarea)
| Key | Action |
|---|---|
| `+` / `=` and `-` | caption size up / down |
| `d` | toggle dark / light theme |
| `l` | cycle caption language |
| `o` | toggle show original |
| `End` or `j` | jump to live |
| `?` | open the shortcuts dialog · `Esc` closes it |

Each control carries `aria-keyshortcuts`; the footer link "Shortcuts (?)" opens the Dialog listing them in the UI language.

### 5.5 Motion and reduced motion
Allowed motion: live dot pulse (2 s), new-line fade-in (150 ms), jump button slide-in (150 ms), smooth scroll. Under `prefers-reduced-motion: reduce` (and always in high contrast): no pulse, no fades, `scroll-behavior: auto`, static skeletons. No autoplay sound, ever.

## 6. State copy (EN · ES neutral · PT-BR), each ≤ 12 words
Keys live in `web/src/i18n/{en,es,pt}.ts` (FR-014-02). `{n}` = seconds, `{stage}` = stage name, `{action}` = start/stop, localized.

| Key | EN | ES | PT-BR |
|---|---|---|---|
| `home.title` | Stages | Escenarios | Palcos |
| `home.lead` | Pick a stage to follow captions in your language. | Elegir un escenario para seguir los subtítulos en su idioma. | Escolha um palco para acompanhar as legendas no seu idioma. |
| `loading.stages` | Loading stages… | Cargando escenarios… | Carregando palcos… |
| `empty.stages` | No stages yet. | Todavía no hay escenarios. | Ainda não há palcos. |
| `empty.stages.hint` | Operators: add stages in stages.yaml. | Operadores: agregar escenarios en stages.yaml. | Operadores: adicione palcos em stages.yaml. |
| `stage.notFound` | This stage doesn't exist. | Este escenario no existe. | Este palco não existe. |
| `stage.notFound.link` | See all stages | Ver todos los escenarios | Ver todos os palcos |
| `backend.unreachable` | Can't reach the server. Retrying in {n} s… | Sin conexión con el servidor. Reintentando en {n} s… | Sem conexão com o servidor. Nova tentativa em {n} s… |
| `conn.connecting` | Connecting… | Conectando… | Conectando… |
| `conn.live` | Live | En vivo | Ao vivo |
| `conn.reconnecting` | Reconnecting… | Reconectando… | Reconectando… |
| `conn.reconnecting.banner` | Connection lost. Reconnecting automatically… | Se perdió la conexión. Reconectando automáticamente… | Conexão perdida. Reconectando automaticamente… |
| `conn.failed` | Can't connect. Reload the page to try again. | No se pudo conectar. Recargar la página para reintentar. | Não foi possível conectar. Recarregue a página para tentar. |
| `captions.waiting` | Waiting for the first captions… | Esperando los primeros subtítulos… | Aguardando as primeiras legendas… |
| `state.idle` | Captions haven't started yet. | Los subtítulos todavía no empezaron. | As legendas ainda não começaram. |
| `state.starting` | Captions are starting… | Los subtítulos están empezando… | As legendas estão começando… |
| `state.stopped` | Captions have ended for this stage. | Los subtítulos de este escenario terminaron. | As legendas deste palco terminaram. |
| `state.stopped.hint` | Operators: export the transcript from the dashboard. | Operadores: exportar la transcripción desde el panel. | Operadores: exporte a transcrição no painel. |
| `state.degraded` | Reduced quality: captions may arrive late or incomplete. | Calidad reducida: los subtítulos pueden llegar tarde o incompletos. | Qualidade reduzida: as legendas podem atrasar ou vir incompletas. |
| `marker.original` | original | original | original |
| `marker.original.tip` | Translation is busy right now, so this line shows the original. | La traducción está saturada; esta línea muestra el texto original. | A tradução está ocupada; esta linha mostra o texto original. |
| `jump.toLive` | Jump to live | Volver al vivo | Voltar ao vivo |
| `jump.new` | {n} new | {n} nuevos | {n} novas |
| `delay.line` | Caption delay: about {p50} s (typical), {p95} s (peak) | Demora: cerca de {p50} s (típica), {p95} s (pico) | Atraso: cerca de {p50} s (típico), {p95} s (pico) |
| `dryRun` | Demo mode: simulated captions, no API key. | Modo demo: subtítulos simulados, sin clave de API. | Modo demo: legendas simuladas, sem chave de API. |
| `admin.signin.error` | That token didn't work. Check ADMIN_TOKEN and try again. | Token incorrecto. Revisar ADMIN_TOKEN e intentar de nuevo. | Token incorreto. Verifique ADMIN_TOKEN e tente novamente. |
| `admin.action.error` | Couldn't {action} "{stage}". Try again. | No se pudo {action} "{stage}". Intentar de nuevo. | Não foi possível {action} "{stage}". Tente novamente. |
| `admin.list.error` | Stage list unavailable. Retrying in {n} s… | Lista de escenarios no disponible. Reintentando en {n} s… | Lista de palcos indisponível. Nova tentativa em {n} s… |
| `admin.empty` | No stages configured. Add them to stages.yaml and restart. | No hay escenarios configurados. Agregarlos en stages.yaml y reiniciar. | Nenhum palco configurado. Adicione em stages.yaml e reinicie. |
| `notFound.page` | Page not found. | Página no encontrada. | Página não encontrada. |

Audience badge labels: Live / En vivo / Ao vivo · Not started / Sin empezar / Não iniciado · Starting / Empezando / Iniciando · Reduced quality / Calidad reducida / Qualidade reduzida · Ended / Finalizado / Encerrado. ROTATING is shown to the audience as Live (internal handoff). Admin keeps the technical codes (IDLE, STARTING, LIVE, ROTATING, DEGRADED, STOPPED) because the runbook uses them.
Spanish rules: infinitives and impersonal forms ("Recargar la página", "No hay…"), never "vos" / "tú" conjugations; "subtítulos", "escenario". Portuguese uses natural "você" imperatives ("Recarregue"), "legendas", "palco". Dates and numbers go through `Intl` with the UI locale.

## 7. Home and Admin

### 7.1 Stage card (Home): content order
1. State badge (icon + audience label) top-right; stage name as `h2` top-left.
2. Talk line when the API provides it (title · speaker), one line, truncated.
3. "Spoken: English" · "Captions: Spanish, Portuguese" (language names only, no tags).
4. "Watching now: 43" only when > 0 (never show a lonely 0 to an audience).
5. Primary button "Open live captions" (full width on phones). "Overlay for OBS" stays a small text link (operators).
6. Optional: the short link as text (QR is on the cut ladder; only if a zero-dependency generator exists).

Card order on Home: active stages first (LIVE, DEGRADED, ROTATING, STARTING), then IDLE, then STOPPED; config order within a group. Skeleton: three cards with a title, two meta rows and a button block.

### 7.2 State badge (shared)
`StateBadge` renders icon + label with the palette of §3 and `data-state`; audience label vs technical code chosen by a `variant` prop (`audience` | `operator`). Icons per the §4 inventory. Minimum 0.75 rem text, 24 px height; the icon is `aria-hidden`.

### 7.3 Admin table: "needs attention" ordering
Rows are sorted by attention rank, then config order:

| Rank | Condition | Row treatment |
|---|---|---|
| 0 | `DEGRADED` | amber left border 3 px, `TriangleAlert` in the state cell |
| 1 | `errors` increased since the previous poll, or `STARTING` / `ROTATING` for > 60 s | amber left border, tooltip "stuck for {n} s" |
| 2 | `LIVE` with `p95_ms` > 4000 | neutral border, latency cell in `--state-degraded` |
| 3 | `LIVE` | green left border |
| 4 | `IDLE`, `STOPPED` | no border, muted name |

Re-sorting happens only when a rank changes and never while any row has a pending action (freeze the order until the action resolves): rows must not move under the operator's pointer. A summary strip above the table: "{live} live · {attention} need attention · {listeners} watching · ${cost}". Errors render as Alerts with the copy of §6 and a retry countdown; the sign-in error appears inline under the token field with `aria-describedby`.

### 7.4 Empty and error states
Home: no stages → mark + `empty.stages` + `empty.stages.hint`; backend down → Alert with countdown while the cards from the last successful poll stay visible (stale data beats a blank page). Admin signed-out: only the sign-in card and the backend line. Admin empty: `admin.empty`. Live: `stage.notFound` with the link back, no captions panel.

## 8. Identity

- **Mark:** a speech bubble (rounded rectangle on a 24-unit grid, corner radius 5, tail at the bottom-left) containing two horizontal bars: the upper bar full width in `--ink`, the lower bar ~60 % width in `--accent`. Reads "two languages, one voice". The monochrome variant uses `currentColor` for both bars. Below 24 px the tail is dropped and the bars thicken (favicon variant). Original vector drawn by us, Apache-2.0 like the rest of the repo.
- **Wordmark:** "Lenguaraz" in the system stack, weight 600, letter-spacing −0.01 em, sentence case; mark height = 1.2 × cap height, gap = bar thickness × 2; never stretched, never with a drop shadow. `branding.yaml: logo_url` replaces the mark in the header (not the favicon/OG, which are static).
- **Files:** `web/public/favicon.svg` (mark, `prefers-color-scheme` media inside the SVG), `favicon-32.png`, `apple-touch-icon.png` (180), `icon-192.png`, `icon-512.png` (maskable, content inside the central 80 %), `og.png` 1200 × 630 ≤ 100 kB (8-bit PNG generated by our own script from the SVG, committed).
- **Meta:** `<title>` "Lenguaraz — live captions in your language"; `description` ≤ 155 chars; `og:title`, `og:description`, `og:image`, `og:type=website`, `twitter:card=summary_large_image`. `theme-color`: dark `#0f172a`, light `#ffffff` (two `<meta>` with `media`), high contrast `#000000` set at runtime by `applyPrefsToDocument`.
- **Manifest** (`manifest.webmanifest`): `name` / `short_name` "Lenguaraz", `start_url` "/", `display` "standalone", `background_color` `#0f172a`, `theme_color` `#0f172a`, `lang` "en", icons 192/512 (+ maskable). No service worker, no offline promise.

## 9. Checklist (spec FR-014-xx and judges' criteria)
Judges' criteria: **QoE** = quality of experience · **A11y** = accessibility · **Lat** = latency visibility.

| Item | FR | Criteria |
|---|---|---|
| Comparison table with ≥ 5 products, adopt/avoid, sources (§1) | FR-014-01 | QoE |
| Palette with computed AA/AAA ratios for dark, light, HC (§3) | FR-014-01, FR-014-06 | A11y |
| Brand override keeps ≥ 4.5:1 via the luminance rule (§3.4) | FR-014-01, FR-012-01 | A11y |
| Type scale, measure, spacing, radius, elevation (§4) | FR-014-01, FR-014-03 | QoE |
| Component inventory on shadcn primitives (§4) | FR-014-01, FR-012-02 | QoE |
| Dictionary module EN/ES/PT-BR, auto-detect, switcher, `<html lang>` (§6) | FR-014-02 | A11y, QoE |
| Stage + language always visible; compact header (§5.1) | FR-014-03 | QoE |
| Newest emphasised, older dimmed, interim distinct, measure ≤ 70 ch (§5.2) | FR-014-03 | QoE, A11y |
| Auto-scroll pause + Jump to live (§5.2) | FR-014-03 / AC-3 | QoE |
| Connection pill + delay line (typical / peak) (§5.1, §6) | FR-014-03 | Lat |
| Keyboard shortcuts with accessible hint (§5.4) | FR-014-03 | A11y |
| Reduced motion handling (§5.5) | FR-014-03 | A11y |
| Skeletons, empty, not found, unreachable with countdown, STOPPED, DEGRADED (§6, §7.4) | FR-014-04 / AC-4 | QoE, Lat |
| "Original" marker explained on hover/focus/tap (§5.2, §6) | FR-014-04 | A11y, Lat |
| Admin sign-in and action errors, row colour + icon, attention ordering (§7.3) | FR-014-04 | QoE |
| Mark, wordmark, favicon set, OG/Twitter meta, manifest, theme-color (§8) | FR-014-05 | QoE |
| Axe on every page state; main chunk ≤ 300 kB gzip; no new endpoint | FR-014-06 / AC-5 | A11y |
| H-UI owner walkthrough of the Lighthouse-style list | FR-014-06 / AC-6 | all |

### What we deliberately do not do
- No gamification, streaks, reactions or "applause".
- No chat, comments or Q&A inside the captions page.
- No autoplay sound, no text-to-speech, no vibration.
- No cookies, analytics, tracking pixels or third-party fonts; only `localStorage` for the viewer's own display preferences.
- No service worker or offline mode (no promise we cannot keep).
- No translation of caption content by the UI (captions come from the backend only).
- No colour-only meaning: every state has an icon and a label.
- No raw formatting knobs (colour pickers, font menus): presets only.
- No logos, screenshots or assets from the products reviewed.

## 10. Related documents
- Spec: [specs/014-ux-excellence/spec.md](../../specs/014-ux-excellence/spec.md) · Design system: [specs/012-design-system/spec.md](../../specs/012-design-system/spec.md)
- Theming and branding: [docs/customization.md](../customization.md) · [examples/branding.example.yaml](../../examples/branding.example.yaml)
- Runtime tokens today: [web/src/index.css](../../web/src/index.css)
