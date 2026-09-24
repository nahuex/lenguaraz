# Quickstart — de la laptop a subtítulos en vivo en 15 minutos

Necesitás Docker (o Python 3.12 + uv + Node 24 para el camino de desarrollo). La API key de
Gemini solo hace falta para transcribir de verdad; el **dry-run** funciona sin credenciales.
La versión en inglés, [docs/deploy/quickstart.md](../deploy/quickstart.md), es la fuente de
verdad; esta es su traducción.

## 1. Dry-run (sin credenciales, 3 comandos)

```bash
git clone https://github.com/nahuex/lenguaraz.git && cd lenguaraz
cp .env.example .env            # después poné ENGINE=fake en .env para el dry-run
docker compose up --build
```

Abrí http://localhost:8000. Vas a ver dos escenarios ("Main Stage" y "Workshop Room") con
una etiqueta **DRY-RUN**. Hacé clic en **Open Fogón · live captions** en un escenario: los
subtítulos aparecen en unos segundos, palabra por palabra, desde los clips incluidos.
`http://localhost:8000/healthz` devuelve `{"status":"ok","engine":"fake","stages":2,…}`.

El dry-run reproduce las transcripciones de referencia que están junto a los archivos de
audio (`samples/*.txt`) al ritmo de habla; ejercita todo el pipeline salvo la llamada a Gemini.

## 2. Transcripción real con Gemini

1. Creá una API key en [Google AI Studio](https://aistudio.google.com/) en un proyecto con
   **facturación habilitada** (el tier gratuito limita las sesiones Live concurrentes y las
   solicitudes diarias, y puede usar el contenido para mejorar productos de Google; ver
   `docs/privacy.md`). Los operadores deben ser mayores de 18 años.
2. Ponela en `.env`: `GEMINI_API_KEY=…` y `ENGINE=gemini`.
3. `docker compose up --build` de nuevo. La etiqueta desaparece y los subtítulos ahora vienen
   de `gemini-3.5-transcribe-live` escuchando el audio de muestra.

Verificá calidad y latencia desde la terminal (usa un poco de cuota):

```bash
make smoke-stt      # transcribe samples/en_kubernetes.wav, imprime WER, percentiles de latencia, tokens
```

## 3. Tus propios escenarios

Editá `stages.yaml` (cada campo está descripto en `docs/configuration.md`):

```yaml
stages:
  - id: main
    name: "Escenario principal"
    source: "srt://0.0.0.0:9000?mode=listener"   # o una URL HLS, rtmp://, un archivo…
    source_lang: ["es-419"]
    targets: ["en", "pt-BR"]
    glossary: ["Kubernetes", "eBPF", "NombreDeTuProducto"]
```

Reiniciá el contenedor (`docker compose restart`). Compartí
`http://<tu-host>:8000/fogon/main` con la audiencia. Cualquier cosa que ffmpeg pueda leer
sirve como `source`; `docs/deploy/audio-sources.md` tiene recetas para OBS, vMix, HLS y SRT.
Para un despliegue público con TLS, `docs/deploy/production.md`; para Google Cloud,
`docs/deploy/cloud-run.md`.

## Camino de desarrollo (sin Docker)

```bash
uv sync                          # entorno Python 3.12 (uv instala Python si hace falta)
make web                         # construye la vista de audiencia (necesita Node 24)
ENGINE=fake make dev             # http://127.0.0.1:8000 con recarga automática
make verify                      # lint, tipos, tests, build del frontend, headers SPDX
```

Hace falta `ffmpeg` en el PATH (o `FFMPEG_BIN=/ruta/a/ffmpeg`) para todo lo que no sea un
WAV mono de 16 kHz.

## Problemas frecuentes

| Síntoma | Causa → solución |
|---|---|
| El escenario muestra `STOPPED` con `cannot open WAV` / `ffmpeg exited` | La ruta o URL del `source` está mal, o falta ffmpeg → corregí la ruta, instalá ffmpeg o definí `FFMPEG_BIN`. |
| El escenario muestra `DEGRADED` con `quota exhausted (429…)` | Límites del tier gratuito o tope de gasto → habilitá facturación en el proyecto, o reducí escenarios concurrentes. |
| El escenario muestra `STOPPED` con `authentication failed` | `GEMINI_API_KEY` incorrecta → pegá la key de AI Studio en `.env`. |
| `ROTATING` por un instante cada ~9 minutos | Normal: la sesión Live dura 10 minutos; Lenguaraz abre la siguiente antes y cambia en una pausa (no se pierde ninguna frase). |
| Los subtítulos se detienen mientras el orador habla | El watchdog reabre la sesión después de `STT_STALL_SECONDS`; si se repite, revisá el nivel de audio (`docs/troubleshooting.md`). |
| La página principal dice "audience view is not built yet" | Ejecutá `make web` (camino de desarrollo); la imagen Docker lo construye sola. |
