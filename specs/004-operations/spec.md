# Spec 004 — operations

**Status:** Shipped · **Owner:** human · **Author:** agent · **Created:** 2026-09-24T21:26Z
**Constitution:** v1.0.0 · **Backlog row:** product.md §6 #004

## 1. Why
A production team needs to see every stage at a glance, start and stop stages, feed the
stream overlay and hand out the transcript after each talk; the challenge lists exactly these
as optional extras ("panel de monitoreo … estado de cada sesión, latencia, errores",
"integración con OBS, vMix … para quemar los subtítulos", "exportar la transcripción completa
… SRT / VTT / texto"). The SRT export is also what produces the English subtitles of the demo
video with Lenguaraz itself (Art. I.6). Moves **Deployment & Operation** and **Innovation**.
Scope-cut ladder applied at planning time: QR codes and the glossary editing UI are cut;
export → status panel → overlay is the build order (export first: the video needs it).

## 2. User stories
- **US-1 (P0)** As an operator, I want to download the transcript of a stage in SRT, VTT or
  plain text for any language it produced, so that I can publish subtitles after the talk.
- **US-2 (P0)** As an operator, I want one page (Mangrullo) that shows every stage's state,
  detail, listeners, active languages, latency, rotations, errors, token usage and estimated
  cost, and lets me start or stop a stage, so that I can run an event without a terminal.
- **US-3 (P1)** As a video producer, I want a transparent browser page (Pizarrón) that shows
  the last lines of captions in a chosen language, so that OBS or vMix can burn subtitles into
  the stream.

## 3. Functional requirements
| ID | Requirement | Traces to |
|---|---|---|
| FR-004-01 | **Acta (transcript store):** each stage MUST keep a bounded in-memory list of final captions per language with `start_ms`/`end_ms` on the audio timeline (start = first partial of the utterance, end = its final), fed from the bus so original and translated finals are both kept; nothing is written to disk unless exported (Art. IX.1). | US-1 |
| FR-004-02 | **Export:** `GET /api/admin/stages/{id}/export?format=srt\|vtt\|txt&lang=<code>` (Bearer `ADMIN_TOKEN`) MUST render the store as valid SRT (`HH:MM:SS,mmm`), WebVTT (`WEBVTT` header, `HH:MM:SS.mmm`) or plain text with a timestamp per line, with `Content-Disposition: attachment`; unknown stage → 404, unknown language → 404 with the list of available languages. | US-1, Art. VIII.2 |
| FR-004-03 | **Mangrullo API:** `GET /api/admin/stages` (Bearer) MUST return the stage snapshots plus `running`, `audio_seconds`, `est_cost_usd` (computed from measured audio seconds and recorded translation tokens with the GT-6 prices and their date) and `transcript_entries` per language; `POST /api/admin/stages/{id}/start` and `/stop` MUST start/stop a stage runner; every admin request without a valid token MUST get 401; tokens are compared in constant time. | US-2, Art. VIII.2, Art. VII.3 |
| FR-004-04 | **Mangrullo page** `/mangrullo`: token entry kept in session storage, table of stages with state/detail/listeners/active languages/captions/latency p50-p95/rotations/errors/duplicates/dropped/tokens/cost, Start/Stop buttons, export buttons per language and format, links to Fogón and Pizarrón; refresh every 3 s. | US-2, Art. XI.3 |
| FR-004-05 | **Pizarrón** `/pizarron/{stage}?lang=&lines=2&size=l&align=bottom&bg=band`: transparent background, no controls, last N finals + interim, large outlined text readable on video, reconnecting socket; misconfiguration shown as a one-line message. | US-3 |
| FR-004-06 | **Docs-as-you-go:** `docs/architecture.md` (Acta, Mangrullo, Pizarrón), `docs/operations/runbook.md` (event-day checklist incl. export after the talk), `docs/customization.md` (overlay parameters), `docs/troubleshooting.md` (401, empty export). | Art. XVII.D.6 |

## 4. Non-functional requirements
| ID | Requirement | Measure |
|---|---|---|
| NFR-004-01 | Export of a 60-minute talk (≈ 600 finals × 3 languages) | < 200 ms, `pytest tests/test_export.py::test_render_is_fast` |
| NFR-004-02 | Admin polling cost | one request per 3 s per open Mangrullo tab; snapshot < 20 ms for 30 stages |
| NFR-004-03 | Overlay readability | white text with dark outline, size ≥ 40 px at 1080p; verified visually at H4 |

## 5. Acceptance criteria (executable)
- **AC-1** Given interims and a final for seq 0 (t_audio 500 → 3,400 ms) and a translated final for the same seq, when recorded, then both languages have one entry with start 500 and end 3,400 — verified by `pytest tests/test_export.py`
- **AC-2** Given three entries, when rendered as SRT, VTT and TXT, then the output matches the golden strings (numbering, `-->`, comma vs dot milliseconds, `WEBVTT` header) — verified by `pytest tests/test_export.py`
- **AC-3** Given no token or a wrong token, when calling any `/api/admin/*` route, then 401 — verified by `pytest tests/test_admin.py`
- **AC-4** Given the token, when `GET /api/admin/stages` runs on two fake stages, then both rows carry `running`, `est_cost_usd` ≥ 0 and `transcript_entries`; `POST …/stop` sets `running` false and state `STOPPED`; `POST …/start` runs it again — verified by `pytest tests/test_admin.py`
- **AC-5** Given a fake stage that produced finals in `en` and `es`, when exporting `?format=srt&lang=es`, then the body contains the translated lines and the attachment header — verified by `pytest tests/test_admin.py::test_export`
- **AC-6** Given the built frontend, when opening `/mangrullo` and `/pizarron/main`, then the pages render and the vitest suites for both pass — verified by `cd web && npm test && npm run build`
- **AC-7** `make docs-check` green; runbook exists — verified by `make docs-check`

## 6. Out of scope
- QR codes, glossary editing UI (ladder cuts), start/stop from the public pages, multi-user admin auth (a single shared `ADMIN_TOKEN`; reverse-proxy auth documented for stricter setups), persistence of transcripts across restarts.

## 7. Open questions
- [x] Q1 Export auth: Bearer only (no `?token=`) → default applied (secure default; the Mangrullo page downloads with the header)
- [x] Q2 Timestamps: audio-timeline positions of first partial/final, no fixed correction → default applied (documented in the runbook)

## Changelog
- 2026-09-24T21:26Z created; Status Approved (non-blocking defaults).
