# Customization

Everything event-specific is configuration: `stages.yaml` for the event, `.env` for the
deployment. Nothing about a particular conference is hardcoded.

## Languages

- **Source language per stage:** `source_lang: ["en-US"]` (a BCP-47 hint gives the best
  accuracy) or `[]` for automatic detection, including speakers who switch languages
  mid-talk. The live transcription model supports 70+ languages (`en-US`, `en-GB`, `es-419`,
  `es-US`, `pt-BR`, `pt-PT`, …).
- **Target languages per stage:** `targets: ["es", "en", "pt"]` (short codes). The audience
  picks among the original and the targets on the live captions page.
- **Always-on languages:** `ALWAYS_ON_LANGS=es` translates those languages even with no
  listener, so a transcript exists for every talk. Every other target is translated only
  while someone is listening (plus a grace period), which keeps cost proportional to demand.
- **Progressive translation:** `PROGRESSIVE_TRANSLATION=true` shows a provisional translated
  line while the speaker is still talking; the final replaces it. Turn it off to translate
  finals only (fewer calls).

## Glossary of technical terms and proper names

Each stage has a `glossary` (≤ 100 terms, ≤ 64 chars each). The list is sent to the
transcription model as `custom_vocabulary`, which biases recognition toward those spellings,
and inserted as delimited data into every translation prompt with the rule "keep every term
exactly as written". Put product names, acronyms, speaker names, the event name and any
word the talk repeats. Terms are data, never instructions: the prompt neutralizes anything
that looks like a command. With `AUTO_GLOSSARY=true` (default) Lenguaraz also derives up to
`AUTO_GLOSSARY_MAX_TERMS` terms from `talk.title` and `talk.abstract` before the stage starts
(structured JSON output from the text model; a deterministic heuristic in dry-run mode) and
merges them after your manual list, so your terms always win and the total stays ≤ 100. The
stage snapshot shows `glossary_terms` and `auto_glossary_terms`.

## Branding

Copy `examples/branding.example.yaml` to `branding.yaml` (or set `BRANDING_FILE`) and set
`event_name`, `tagline`, `primary_color`, `logo_url` and `footer`. Put logo files in
`branding/local/` (git-ignored, served at `/branding/`) or use an `https://` URL. The Docker
image reads `branding.yaml` from the working directory; mount it read-only like `stages.yaml`
(`- ./branding.yaml:/app/branding.yaml:ro`). Field validation is listed in `docs/configuration.md`.

```yaml
glossary: ["Kubernetes", "eBPF", "Cilium", "CoreDNS", "Nerdearla", "Ana Pérez"]
```

## Talk metadata

`talk.title` and `talk.abstract` give the translation model context (terminology, tense).
They are capped and delimited like the glossary.

## Look and feel

The audience view ships with a neutral dark theme, a light theme and a high-contrast theme
(WCAG 2.1 AA), font-size control and a "show original" toggle; every preference is stored in
the visitor's browser. Event branding (name, colors, logo) is runtime configuration
(`branding.yaml`, feature 008); logos are never committed to the repository.

## Theming

The pages are built on [shadcn/ui](https://ui.shadcn.com) (MIT) primitives over Tailwind
CSS 4. Every colour, radius and font is a CSS variable in `web/src/index.css`; the components
never carry a hardcoded colour, so a conference re-themes the pages by editing tokens, not
components.

**Where the themes live.** `index.css` declares the shadcn variables (`--background`,
`--foreground`, `--card`, `--primary`, `--primary-foreground`, `--secondary`, `--muted`,
`--accent`, `--destructive`, `--border`, `--input`, `--ring`, `--radius`, …) in three blocks,
switched by data attributes that `web/src/lib/prefs.ts` sets on `<html>` from the viewer's
saved preferences:

| Block | Selector | When |
|---|---|---|
| Dark (default) | `:root` | No attribute, or `data-theme="dark"` |
| Light | `:root[data-theme="light"]` | The viewer turns "Dark theme" off |
| High contrast | `:root[data-contrast="high"]` | The viewer turns "High contrast" on; wins over the theme |

The `dark:` utility variant follows the same attributes, and high contrast always renders on
black. Two Lenguaraz tokens sit next to the shadcn set: `--caption-size` (the caption font
size, switched by `data-font-size="S|M|L|XL"`, exposed as the `text-caption` utility) and
`--focus` (the outline of the base `:focus-visible` rule). Keep the pairs at WCAG 2.1 AA
(≥ 4.5:1) in the dark and light blocks and AAA (≥ 7:1) in the high-contrast block; the
Overlay page keeps its own transparent CSS (`web/src/pages/overlay.css`) because it renders
inside OBS.

**Branding → `--primary`.** At runtime `web/src/lib/useBranding.ts` reads `primary_color`
from `GET /api/branding` (`branding.yaml`) and sets `--primary` and `--ring` on `<html>`,
plus a black or white `--primary-foreground` chosen by WCAG relative luminance, so buttons,
the live badge, the selected font size and the brand stripe in the header take the event's
colour without a rebuild. When high contrast is on, the overrides are removed and the AAA
yellow-on-black pair from `index.css` stays in force: accessibility beats branding.

**Adding a primitive.** Components live in `web/src/components/ui/` and are copied, not
installed, so they can be edited like any other file:

```bash
cd web && npx shadcn@latest add <name>   # e.g. dialog, tooltip, select
```

The CLI writes the file with double quotes and no header. Before committing, add the two
header lines every file under `ui/` carries, then run Prettier:

```tsx
// SPDX-License-Identifier: Apache-2.0
// Derived from shadcn/ui (https://ui.shadcn.com) — MIT License, Copyright (c) 2023 shadcn
```

`make spdx-check` fails without the first line; the second keeps the MIT attribution that
`NOTICE` promises. If the component pulls a new package, check its license against the
allowlist and run `make license-check` (see `CONTRIBUTING.md`). Pages import primitives from
`@/components/ui/<name>` and compose them; nobody hand-rolls a button or an input.

## OBS / vMix overlay

Add a **Browser Source** pointing at `http://<host>:8000/overlay/<stage>?lang=es&lines=2`
with the canvas size of your scene; the page background is transparent. Parameters:

| Parameter | Values | Default | Meaning |
|---|---|---|---|
| `lang` | short code | first source language | Caption language |
| `lines` | 1–5 | `2` | Final lines kept on screen (plus the current partial) |
| `size` | `s` `m` `l` `xl` | `l` | Font size (28/40/56/72 px at 1080p) |
| `align` | `bottom` `top` | `bottom` | Where the block sits |
| `bg` | `band` `none` | `band` | Semi-transparent band behind the text, or nothing |
