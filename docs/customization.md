# Customization

Everything event-specific is configuration: `stages.yaml` for the event, `.env` for the
deployment. Nothing about a particular conference is hardcoded.

## Languages

- **Source language per stage:** `source_lang: ["en-US"]` (a BCP-47 hint gives the best
  accuracy) or `[]` for automatic detection, including speakers who switch languages
  mid-talk. The live transcription model supports 70+ languages (`en-US`, `en-GB`, `es-419`,
  `es-US`, `pt-BR`, `pt-PT`, …).
- **Target languages per stage:** `targets: ["es", "en", "pt"]` (short codes). The audience
  picks among the original and the targets on the Fogón page.
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
that looks like a command. Feature 006 builds a first glossary automatically from the talk
title and abstract; feature 004 lets operators edit it live.

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

## OBS / vMix overlay (Pizarrón)

Add a **Browser Source** pointing at `http://<host>:8000/pizarron/<stage>?lang=es&lines=2`
with the canvas size of your scene; the page background is transparent. Parameters:

| Parameter | Values | Default | Meaning |
|---|---|---|---|
| `lang` | short code | first source language | Caption language |
| `lines` | 1–5 | `2` | Final lines kept on screen (plus the current partial) |
| `size` | `s` `m` `l` `xl` | `l` | Font size (28/40/56/72 px at 1080p) |
| `align` | `bottom` `top` | `bottom` | Where the block sits |
| `bg` | `band` `none` | `band` | Semi-transparent band behind the text, or nothing |
