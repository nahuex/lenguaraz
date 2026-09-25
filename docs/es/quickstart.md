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
una etiqueta **DRY-RUN**. Hacé clic en **Open live captions** en un escenario: los
subtítulos aparecen en unos segundos, palabra por palabra, desde los clips incluidos.
`http://localhost:8000/healthz` devuelve `{"status":"ok","engine":"fake","stages":2,…}`.

El dry-run reproduce las transcripciones de referencia que están junto a los archivos de
audio (`samples/*.txt`) al ritmo de habla; ejercita todo el pipeline salvo la llamada a Gemini.

## 2. Transcripción real con Gemini

1. Creá una API key en [Google AI Studio](https://aistudio.google.com/) en un proyecto con
   **facturación habilitada** (el tier gratuito limita las sesiones Live concurrentes y las
   solicitudes diarias, y puede usar el contenido para mejorar productos de Google; ver
   `docs/privacy.md`). Los operadores deben ser mayores de 18 años.
   Las cuentas de facturación nuevas de AI Studio son **prepagas**: comprá al menos USD 5 de
   créditos (AI Studio → Facturación → **Comprar créditos**) o cada llamada responde
   `402 prepayment credits are depleted`, aunque la facturación esté vinculada.
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
    targets: ["en", "pt"]            # códigos cortos: en, es, pt
    glossary: ["Kubernetes", "eBPF", "NombreDeTuProducto"]
```

Reiniciá el contenedor (`docker compose restart`).

Para compartirlo con la audiencia poné HTTPS adelante: el stack de Compose escucha solo en
`127.0.0.1:8000`, y `docker compose --profile tls up -d` (con `DOMAIN` y `ACME_EMAIL` en
`.env`) obtiene un certificado de Let's Encrypt; o usá el tuyo con `TLS_CERT_FILE`/`TLS_KEY_FILE`
(los dos caminos en `docs/deploy/production.md`, sección 3). Para una demo en HTTP dentro de una
red local, publicá el puerto con un `docker-compose.override.yml`
(`ports: !override ["8000:8000"]`) y compartí `http://<tu-host>:8000/live/main`.

Cualquier cosa que ffmpeg pueda leer
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
| Faltan frases en una vista traducida / el detalle dice `rate limited (429)` | El proyecto de Gemini está en el **tier gratuito** para el modelo de texto (`generate_content_free_tier_requests`, 15 solicitudes/min): la traducción se pausa el tiempo que pide el servidor y mientras tanto esas frases se omiten en ese idioma → vinculá una cuenta de facturación de Cloud al proyecto de AI Studio (Tier 1) y comprá créditos prepagos; para seguir en el tier gratuito, arrancá desde `examples/env/free-tier.env` y mirá un solo escenario y un solo idioma a la vez. |
| Todos los escenarios en `STOPPED`/`DEGRADED` con `402 … prepayment credits are depleted` | La cuenta de facturación es prepaga con saldo USD 0 → comprá créditos (mínimo USD 5) en https://aistudio.google.com/billing; con saldo prepago, los créditos de Cloud se consumen primero. Alternativa: desvinculá el proyecto → tier gratuito. |
| El escenario muestra `STOPPED` con `authentication failed` | `GEMINI_API_KEY` incorrecta → pegá la key de AI Studio en `.env`. |
| `ROTATING` por un instante cada ~9 minutos | Normal: la sesión Live dura 10 minutos; Lenguaraz abre la siguiente antes y cambia en una pausa (no se pierde ninguna frase). |
| Los subtítulos se detienen mientras el orador habla | El watchdog reabre la sesión después de `STT_STALL_SECONDS`; si se repite, revisá el nivel de audio (`docs/troubleshooting.md`). |
| La página principal dice "audience view is not built yet" | Ejecutá `make web` (camino de desarrollo); la imagen Docker lo construye sola. |
