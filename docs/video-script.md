# Demo video script (1:45) — with English subtitles exported from Lenguaraz

Recorded by the owner at checkpoint H4. Screen capture at 1080p, one take per section,
cut together with the on-screen text below. Voice: Rioplatense Spanish (the English SRT is
produced by Lenguaraz itself, see the last section).

## Setup before recording

```bash
cp examples/env/production.env .env      # ENGINE=gemini, your key, a real ADMIN_TOKEN
docker compose up --build -d
```

`stages.yaml` as shipped (Main Stage EN → es/pt, Workshop ES → en/pt, both looping the
bundled samples). Open four browser tabs: `/`, `/live/main`, `/live/workshop`,
`/admin`. OBS with a browser source on `/overlay/main?lang=es&lines=2&size=48`.

## Shot list

| Time | Screen | Voice-over (ES) | On-screen text (EN) |
|---|---|---|---|
| 0:00–0:10 | Title card: "Lenguaraz — every stage, every language" over the Home page | "Una conferencia tiene varios escenarios y gente que no habla el idioma del orador. Lenguaraz pone subtítulos en vivo, traducidos, en el teléfono de cada persona." | Open source · Apache-2.0 · Gemini Live API |
| 0:10–0:35 | Live captions `/live/main` full screen; captions appear word by word; switch language picker EN → ES | "Este es el escenario principal. Los subtítulos parciales aparecen mientras el orador habla, y cada frase se confirma en una pausa. Cambio a español y la traducción sigue en vivo." | `gemini-3.5-transcribe-live` · partials ≈ 1 s · finals at every pause · translation with `gemini-3.5-flash-lite` |
| 0:35–0:50 | Live captions `/live/workshop` (Spanish talk) with English selected; font size XL, high contrast | "El taller es en español; la audiencia lo lee en inglés. Fuente grande, alto contraste, lector de pantalla: accesibilidad primero." | Any language pair · glossary keeps `TaskGroup`, `Nerdearla` right |
| 0:50–1:05 | OBS program with the Overlay burned in | "Para el streaming, un overlay transparente para OBS con el idioma y el número de líneas que quieras." | `/overlay/main?lang=es&lines=2` |
| 1:05–1:25 | Admin `/admin`: table with both stages LIVE, latency p50/p95, rotations, cost; click Export SRT | "El panel de operación muestra cada escenario, la latencia medida, las rotaciones de sesión cada diez minutos que pasan sin perder frases, y el costo estimado. Y exporta la transcripción en SRT." | Measured: WER 3.2 % · rotation 0 lost / 0 duplicated · USD 0.50 per stage-hour |
| 1:25–1:40 | Terminal: `make simulate` report + `docs/scale-report.md` | "Diez escenarios en un proceso: diez por ciento de un core. Todo está documentado para que cualquier conferencia lo despliegue sola." | 10 stages · 10 % CPU · deploy docs for any conference |
| 1:40–1:45 | README on GitHub, license badge | "Lenguaraz. Abierto, medido y listo para tu evento." | github.com/nahuex/lenguaraz |

## Exporting the English SRT of this very video

The subtitles of the video are produced by Lenguaraz, not by an editor:

1. Add a stage that listens to the narration (microphone via SRT, see
   `docs/deploy/audio-sources.md`) with `source_lang: ["es-419"]` and `targets: ["en"]`, or
   simply feed the recorded narration file as `source`.
2. Start it from the Admin page, let the narration play once, stop it.
3. Admin → the stage row → **Export SRT** with language `en`
   (`GET /api/admin/stages/<id>/export?format=srt&lang=en` behind the Bearer token).
4. Upload the `.srt` to YouTube as the English subtitle track; keep the file in the
   Devpost submission as evidence.

Timestamps in the SRT are relative to the stage start, so start the stage together with the
recording (or offset them in the editor).
