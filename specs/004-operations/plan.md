# Plan 004 — operations

**Spec:** specs/004-operations/spec.md (Approved) · **Created:** 2026-09-24T21:27Z

## 1. Constitution check (gate — all must be ✅ before tasks)
| Article | Status | Note |
|---|---|---|
| I Compliance | ✅ | Covers the challenge's optional extras (monitoring panel, OBS overlay, SRT/VTT/text export); export produces the video's EN subtitles |
| II Google terms | ✅ | No new Google surface |
| III SDD traceability | ✅ | Tasks reference FR-004-xx / AC-x |
| IV Docs-verified | ✅ | No Gemini API surface added |
| V Performance budgets | ✅ | Export and snapshot budgets in NFR-004-01/02 |
| VI Resilience | ✅ | Start/stop reuse the runner; stopping never affects other stages |
| VII Scale & cost | ✅ | `est_cost_usd` from measured audio seconds and tokens with GT-6 prices (dated) |
| VIII Security | ✅ | Bearer `ADMIN_TOKEN`, constant-time compare, 401 on failure; audience routes untouched; overlay is read-only |
| IX Privacy | ✅ | Transcript store bounded in memory; written only on explicit export |
| X Accessibility | ✅ | Mangrullo keyboard accessible, AA tokens; overlay contrast by design |
| XI Operability | ✅ | Operator can start/stop/monitor/export from one page |
| XII Tests | ✅ | Store, renderers, admin routes, export; vitest for both pages |
| XIII Simplicity | ✅ | Store fed from the bus (no new event type); admin routes are thin wrappers over `StageManager` |
| XVII Open source & deployability | ✅ | No new deps; SPDX headers; runbook + docs in the same feature |

## 2. Verified references (Article IV)
| API surface used | Verified via | URL / MCP query | Ground-truth ref |
|---|---|---|---|
| Pricing for the cost estimate | GT re-verified at T-000 | `ai.google.dev/gemini-api/docs/pricing` | GT-6.1, GT-6.3 |
| (no Gemini surface) | — | — | — |

## 2b. Prior art applied
| Lesson / pattern (prior-art.md) | How this feature applies or improves it |
|---|---|
| PA-1 L9 simple password for broadcasters; IAP for lockdown | `ADMIN_TOKEN` Bearer; reverse-proxy/IAP documented in production docs (008) |
| PA-1 gap: no export, overlay or latency metrics | Acta export, Pizarrón overlay, p50/p95 + rotation/error counters in Mangrullo |

## 3. Design
- `lenguaraz/export.py` (Acta): `TranscriptEntry(seq, lang, text, start_ms, end_ms)`, `TranscriptStore(max_entries=5000)`: `record(CaptionEvent)` keeps `starts[seq]` from the first partial (bounded dict) and appends finals per language; `languages()`, `entries(lang)`, `render(lang, fmt)` with `to_srt`, `to_vtt`, `to_txt` and `format_timestamp(ms, sep)`.
- `runner.py`: `StageRunner.transcript` fed by a bus subscription task created at `start()`; snapshot adds `running`, `audio_seconds`, `est_cost_usd`, `transcript_entries`.
- `lenguaraz/pricing.py`: GT-6 prices with the date; `estimate_stage_cost(audio_seconds, stt_response_tokens, translation_usage)`.
- `lenguaraz/api/admin.py` (Mangrullo): `require_admin` dependency (`hmac.compare_digest` on the Bearer token), routes `GET /api/admin/stages`, `POST /api/admin/stages/{id}/start|stop`, `GET /api/admin/stages/{id}/export`.
- `web/src/pages/Mangrullo.tsx`, `web/src/pages/Pizarron.tsx`, `web/src/lib/api.ts` additions (built by the frontend agent from the contract in the spec).
- Docs: `docs/operations/runbook.md` (new), architecture/customization/troubleshooting updates.

## 4. Contracts
See spec §3 FR-004-02/03 and the frontend contract (admin snapshot fields, export headers, close codes).

## 5. Dependencies added (justify each)
| Package | Version | License (SPDX) | Allowed per Art. XVII.B? | Why |
|---|---|---|---|---|
| — | — | — | — | none |

## 6. Risks & mitigations
| Risk | Likelihood | Mitigation |
|---|---|---|
| Timestamps drift for long streams (audio timeline vs wall clock) | Low | Timeline is bytes-based; documented; VTT/SRT consumers only need relative times |
| Bus backlog eviction drops interims before the store sees them | Low | The store subscription is consumed immediately; finals are never dropped |
| Export of a stage that never produced a language | Low | 404 with the list of available languages |

## 7. Verification strategy
Unit tests for the store and renderers (golden strings), TestClient tests for admin auth, start/stop and export; vitest for both pages; `make verify` + `make docs-check`.
