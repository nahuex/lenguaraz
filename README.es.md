# Lenguaraz

*El intérprete open source para todos los escenarios.*

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![CI](https://github.com/nahuex/lenguaraz/actions/workflows/ci.yml/badge.svg)](https://github.com/nahuex/lenguaraz/actions/workflows/ci.yml)
[Read in English](README.md)

Lenguaraz convierte el audio de cada escenario de una conferencia en subtítulos en vivo, en
el idioma que se habla y traducidos a los idiomas que la audiencia pida. Un archivo YAML
describe los escenarios, un comando levanta todo, y cada asistente abre un link en su
teléfono, elige escenario e idioma, y lee.

En la frontera rioplatense de los siglos XVIII y XIX, el *lenguaraz* era el intérprete que
se paraba entre pueblos que no compartían lengua, para que todos en un parlamento pudieran
seguir lo que se decía. Ese es exactamente el trabajo de este sistema: alguien habla en un
escenario y cada persona lo entiende en su idioma.

> **Estado:** construido durante la ventana de la Nerdearla Vibeathon 2026 (24-09-2026 15:00
> UTC → 25-09-2026 15:00 UTC). Las funcionalidades llegan en orden; este README dice qué
> funciona hoy. El README en inglés es la fuente de verdad; esta es su traducción.

## Qué hace hoy

- **Transcripción en vivo** de cualquier fuente de audio que la conferencia ya tenga
  (archivo, HLS, RTMP, SRT o un dispositivo) con `gemini-3.5-transcribe-live` de Google sobre
  la Live API: subtítulos parciales mientras el orador habla, una línea confirmada en cada
  pausa, glosario por escenario para sesgar el reconocimiento.
- **Muchos escenarios a la vez**, cada uno en su pipeline aislado con estado visible
  (`IDLE · STARTING · LIVE · ROTATING · DEGRADED · STOPPED`) y reconexión automática.
- **Subtítulos en vivo (vista de audiencia):** selector de escenario e idioma, tamaño de
  fuente, alto contraste, modo oscuro, subtítulos accesibles para lectores de pantalla,
  WebSocket con reconexión.
- **Traducción en vivo** a cualquier cantidad de idiomas con `gemini-3.5-flash-lite`:
  en streaming, respetando el glosario, con las frases anteriores como contexto; solo se
  traduce mientras alguien escucha (o si el idioma está en `ALWAYS_ON_LANGS`), y una falla de
  traducción degrada al texto original en vez de silencio.
- **Rotación de sesión sin cortes:** la Live API cierra la sesión a los ~10 minutos;
  la siguiente se abre antes, el cambio ocurre en una pausa y los finales se drenan y
  deduplican. Medido con el motor real: 0 frases perdidas, 0 duplicadas en rotaciones forzadas.
- **Admin (panel de operación)** detrás de un Bearer token: tabla de escenarios con
  estado, latencia y costo estimado, start/stop, exportación de transcripciones **SRT / VTT /
  TXT** por idioma.
- **Overlay (para OBS):** una página transparente para browser source con
  `?lang=&lines=&size=`.
- **Auto-glosario:** términos técnicos y nombres propios derivados del título y
  el abstract de la charla con salida estructurada de Gemini, agregados después de tu lista
  manual.
- **Modo dry-run** (`ENGINE=fake`) que ejercita toda la interfaz sin credenciales.
- **Medido, no prometido:** `make smoke-stt` reporta tasa de error de palabras (WER), latencia
  del primer parcial y de fin de frase a subtítulo final, y uso de tokens contra los clips
  incluidos; `make simulate` corre diez escenarios en un proceso y escribe un reporte de
  CPU/RSS/costo (`docs/metrics.md`, `docs/scale-report.md`, `docs/cost.md`).

## Quickstart (3 comandos)

```bash
git clone https://github.com/nahuex/lenguaraz.git && cd lenguaraz
cp .env.example .env      # poné GEMINI_API_KEY=… (o ENGINE=fake para un dry-run sin credenciales)
docker compose up --build
```

Después abrí http://localhost:8000 y hacé clic en **Open live captions** en un escenario.
Recorrido completo, camino de desarrollo y resolución de problemas:
[docs/es/quickstart.md](docs/es/quickstart.md).

**Requisitos:** Docker (o Python 3.12 + [uv](https://docs.astral.sh/uv/) + Node 24 + ffmpeg
para el camino de desarrollo). **Credenciales:** una API key de Gemini de
[Google AI Studio](https://aistudio.google.com/), guardada del lado del servidor en `.env`;
usá un proyecto con facturación habilitada para eventos reales. **Modelos** (todos
configurables): `gemini-3.5-transcribe-live` (subtítulos), `gemini-3.5-flash-lite`
(traducción), `gemini-3.8-flash-lite-tts` (audio de prueba).

## Componentes

Cada componente lleva un nombre estándar en la superficie (interfaz, rutas, docs) y un
módulo técnico en el código:

| Componente | Código | Qué hace |
|---|---|---|
| Ingesta de audio | `lenguaraz/ingest/` | ffmpeg o lector de WAV → chunks PCM mono de 16 kHz |
| Transcripción | `lenguaraz/stt/` | Sesión de la Gemini Live API: subtítulos parciales y finales, VAD híbrido, rotación de sesión, watchdog de estancamiento |
| Traducción | `lenguaraz/translate/` | Workers por idioma, prompts que respetan el glosario, según demanda (solo los idiomas con oyentes) |
| Bus de eventos | `lenguaraz/bus/` | Fan-out acotado a los clientes WebSocket; los parciales pueden descartarse, los finales nunca |
| Glosario | `lenguaraz/glossary/` | Lista manual + auto-glosario a partir del título y el abstract de la charla (salida estructurada) |
| Exportación de transcripciones | `lenguaraz/export.py` | Transcripción en memoria por escenario e idioma, SRT/VTT/TXT |
| Página de subtítulos en vivo | `web/src/pages/LiveCaptions.tsx` (`/live/{stage}`) | Vista de audiencia: escenario, idioma, tamaño de fuente, contraste, modo oscuro |
| Overlay (para OBS) | `web/src/pages/Overlay.tsx` (`/overlay/{stage}`) | Browser source transparente para OBS/vMix |
| Admin (panel de operación) | `web/src/pages/Admin.tsx`, `lenguaraz/api/admin.py` (`/admin`) | Panel de operación detrás de `ADMIN_TOKEN`: estados, latencia, costo, start/stop, exportaciones |

## Arquitectura en una imagen

```
stages.yaml ─▶ un pipeline aislado por escenario:
  Ingesta (ffmpeg / WAV) ─▶ Transcripción (Gemini Live STT, parcial + final) ─▶ Bus de eventos ─▶ WS /ws/{stage}?lang=
                                                                                                   └▶ Subtítulos en vivo (audiencia)
```

Detalles, contrato de eventos y endpoints: [docs/architecture.md](docs/architecture.md).
Cada configuración y cada campo de `stages.yaml`: [docs/configuration.md](docs/configuration.md).

## Escalar a más escenarios

Cada escenario es un pipeline aislado (un proceso ffmpeg, una sesión de transcripción Live,
un worker de traducción por idioma activo) dentro del mismo proceso: agregar un escenario es
agregar una entrada a `stages.yaml`; dos vienen por defecto y diez se ven exactamente igual.
Lo que crece con la cantidad de escenarios es (1) CPU para decodificar con ffmpeg, unos 2–5 %
de un core por stream, (2) memoria, unas decenas de MB por escenario, y (3) el límite de
sesiones Live concurrentes de tu proyecto de Gemini, que es por proyecto y por tier y se ve
en Google AI Studio (el tier gratuito permite solo unas pocas; usá un proyecto pago para
eventos reales). Más allá de una máquina, corré varias instancias, cada una con su subconjunto
de `stages.yaml`, detrás de cualquier balanceador HTTP: los escenarios no comparten estado y
los subtítulos son eventos WebSocket simples. El costo crece con los escenarios, no con
escenarios × idiomas: un stream de transcripción por escenario alimenta todos los idiomas
como texto. El reporte de `make simulate` (`docs/scale-report.md`: diez escenarios, dos
reales y ocho simulados, ≈10 % de un core y +18 MB de RSS) y la tabla de dimensionamiento
en `docs/deploy/scaling.md` le ponen números medidos a esto.

## Glosario técnico y nombres propios

Las charlas están llenas de términos que el reconocimiento de voz genérico destroza ("eBPF",
"CoreDNS", nombres de personas y productos). Cada escenario lleva una lista `glossary` en
`stages.yaml`; Lenguaraz la manda al modelo de transcripción como `custom_vocabulary` y la
inserta, bien delimitada, en cada prompt de traducción con la instrucción de conservar esos
términos tal cual. Con `AUTO_GLOSSARY=true` (default) la lista se extiende automáticamente
desde el `title` y el `abstract` de la charla (salida JSON estructurada de Gemini; los
términos manuales siempre ganan; máximo 100). `make smoke-stt --glossary none|manual|auto`
y `make smoke-translate` reportan cuántas veces los términos salen bien; en el clip en
español, el glosario convirtió "task group" en `TaskGroup` y "nerdctl" en `Nerdearla`
(`docs/metrics.md`).

## Audio de prueba

`samples/` trae dos charlas cortas generadas con Gemini TTS a partir de guiones originales
escritos para este proyecto (inglés: Kubernetes y eBPF; español: asyncio en Python), con
transcripciones de referencia y límites exactos de cada oración. Se publican bajo Apache-2.0
como todo lo demás. Se regeneran con `make samples`.

## Documentación

Escrita para un líder técnico voluntario de una conferencia que nunca conocimos:

| Desplegar | Operar | Entender |
|---|---|---|
| [Quickstart en español](docs/es/quickstart.md) · [English](docs/deploy/quickstart.md) | [Runbook de operaciones](docs/operations/runbook.md) | [Arquitectura](docs/architecture.md) |
| [Producción (VM + Compose + TLS)](docs/deploy/production.md) | [Resolución de problemas](docs/troubleshooting.md) | [Referencia de configuración](docs/configuration.md) |
| [Cloud Run](docs/deploy/cloud-run.md) | [Personalización: idiomas, glosario, branding, overlay](docs/customization.md) | [Costo por escenario-hora](docs/cost.md) · [Métricas](docs/metrics.md) · [Reporte de escala](docs/scale-report.md) |
| [Escalar a 30+ escenarios](docs/deploy/scaling.md) | [Seguridad](docs/security.md) · [Privacidad](docs/privacy.md) · [SECURITY.md](SECURITY.md) | [Decisiones](docs/decisions.md) · [Changelog](CHANGELOG.md) |
| [Fuentes de audio: SRT, RTMP, HLS, OBS, archivos](docs/deploy/audio-sources.md) | [Ejemplos: escenarios, branding, perfiles .env](examples/) | [Contribuir](CONTRIBUTING.md) · [Código de conducta](CODE_OF_CONDUCT.md) |

`make docs-check` verifica que este conjunto exista, que cada configuración esté documentada
y que cada link resuelva; `make fresh-clone-test` clona el repo público en un directorio
vacío y sigue el quickstart en modo dry-run hasta que fluyen los subtítulos.

## Seguridad y privacidad

La API key de Gemini vive solo en el servidor. Los endpoints de audiencia son de solo lectura
y con límite por IP. El audio nunca se escribe a disco; los subtítulos viven en un buffer en
memoria acotado y solo se loguean con `LOG_TRANSCRIPTS=true`. La API de Gemini exige que los
operadores sean **mayores de 18 años** y los despliegues no deben dirigirse a menores. En el
tier gratuito Google puede usar el contenido para mejorar sus productos; usá un **proyecto
pago** para eventos reales.

## Limitaciones

- **Un proceso es dueño de sus escenarios.** Para escalar horizontalmente, varias instancias
  con archivos `stages.yaml` disjuntos; todavía no hay bus compartido (planificado, recortado
  del alcance del hackathon).
- **Los subtítulos no se persisten.** Exportá SRT/VTT/TXT desde Admin antes de detener un
  escenario.
- **La latencia depende de la fuente.** Medida ≈0,9 s desde el fin de una oración hasta su
  subtítulo final con audio limpio (`docs/metrics.md`); las entradas HLS suman la duración de
  sus segmentos.
- **La calidad depende del audio y del glosario.** Una cama musical o un micrófono lejano
  perjudican más que cualquier configuración; el glosario arregla nombres, no ruido.
- **La Live API tiene varianza.** A veces una sesión se queda muda; el watchdog la reabre
  después de `STT_STALL_SECONDS` y el operador lo ve como `stalls` en Admin.
- **Las sesiones concurrentes son una cuota del proyecto de Google**, por tier; planificalas
  antes del evento (`docs/deploy/scaling.md`).
- La interpretación hablada, la ingesta desde el micrófono del navegador y un fallback
  offline están especificados en el backlog pero no construidos.

## Antecedentes y agradecimientos

Antes de que abriera la ventana leímos dos proyectos públicos para aprender, nunca para
copiar código; cada línea de este repo se derivó de la documentación oficial de Gemini
(`.specify/memory/prior-art.md` registra qué adoptamos y qué hacemos distinto):

- **`gemini-live-translate-livekit` de Google** (Apache-2.0): una sesión de modelo por idioma
  compartida por todos los oyentes, subtítulos en un canal separado del audio, escrituras de
  audio serializadas, flags de Cloud Run para sesiones largas. Nos quedamos con las ideas y
  sacamos el servidor de medios WebRTC: los subtítulos son texto, alcanza con un WebSocket
  detrás de cualquier balanceador.
- **Los ejemplos `gemini-live-translate` y `live-translated-captioning` de LiveKit** (MIT):
  la creación y baja bajo demanda de workers de traducción y el contrato de subtítulos
  parcial/final.
- **`gemini-live-api-examples` de Google**: las formas de los eventos de la Live API que
  verificamos contra el SDK antes de escribir el ground truth.

Gracias al equipo de Nerdearla por un desafío que trata sobre acceso, y a Google por la Live
API y los créditos de AI Studio que pagaron las mediciones de este repo.

## Cómo está construido este repo

Todo lo que hay en este repositorio se creó dentro de la ventana de la Vibeathon (24-09-2026
15:00 UTC a 25-09-2026 15:00 UTC); el historial de git es la evidencia. Antes de la ventana,
el equipo solo leyó las reglas del desafío, la documentación pública de la API de Gemini y dos
proyectos de ejemplo públicos para sacar lecciones; esas notas están fechadas en
`.specify/memory/` y no contienen código.

Desarrollo guiado por especificaciones con una tripulación de ingeniería de IA y un dueño
humano: cada funcionalidad recorre `spec.md → plan.md → tasks.md → loop de implementación`,
con una constitución como ley suprema. Ver [CLAUDE.md](CLAUDE.md), la
[constitución](.specify/memory/constitution.md), el
[ground truth](.specify/memory/ground-truth.md) de hechos verificados de la API y el
[brief de producto](.specify/memory/product.md). Las decisiones quedan en
[docs/decisions.md](docs/decisions.md).

## Licencia

Apache License 2.0 — ver [LICENSE](LICENSE) y [NOTICE](NOTICE). Gemini es un servicio
alojado de Google con sus propios términos; el código que habla con él es open source.
