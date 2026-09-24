# Plan 003 — resilience

**Spec:** specs/003-resilience/spec.md (Approved) · **Created:** 2026-09-24T21:05Z

## 1. Constitution check (gate — all must be ✅ before tasks)
| Article | Status | Note |
|---|---|---|
| I Compliance | ✅ | Inside the window; no new media |
| II Google terms | ✅ | Same server-side key; two overlapping sessions per stage for ≤ 3 s |
| III SDD traceability | ✅ | Tasks reference FR-003-xx / AC-x |
| IV Docs-verified | ✅ | Only surfaces already verified in plan 001 §2 (`connect`, `send_realtime_input`, `audio_stream_end`, `GoAway.time_left`); no new API field |
| V Performance budgets | ✅ | Gap measured on the audio timeline by the smoke tool; `last_rotation_gap_ms` live |
| VI Resilience | ✅ | This feature implements Art. VI.1 make-before-break; VI.2–4 already in 001 |
| VII Scale & cost | ✅ | Overlap cost bounded and documented (NFR-003-03) |
| VIII Security | ✅ | No new inputs |
| IX Privacy | ✅ | No new data retained; dedupe window keeps ≤ 20 normalized strings in memory |
| X Accessibility | ✅ | No UI change |
| XI Operability | ✅ | `ROTATING` visible; rotation logged with both session ids; new keys documented |
| XII Tests | ✅ | Scripted sessions cover rotation, drain, dedupe, open failure, backlog |
| XIII Simplicity | ✅ | One event (`rotate_requested`), one active-session pointer, one dedupe deque |
| XVII Open source & deployability | ✅ | SPDX headers; docs updated in the same commits |

## 2. Verified references (Article IV)
| API surface used | Verified via | URL / MCP query | Ground-truth ref |
|---|---|---|---|
| Session lifetime ~10 min, `GoAway.time_left` before termination | MCP `gemini_get_doc` (plan 001) | `gemini-api-guides/live-api/session-management.md#receiving-a-message-before-the-session-disconnects` | GT-5.1–5.2 |
| `send_realtime_input(audio_stream_end=True)` finalizes the pending turn | MCP `gemini_get_doc` (plan 001) | `gemini-api-guides/live-api/live-transcribe.md#voice-activity-detection-vad-strategies` | GT-2.4 |
| Best practice: "handle GoAway messages … use the timeLeft field to gracefully wrap up" | MCP `gemini_search_docs` | `gemini-api-guides/live-api/best-practices.md#session-management` | GT-5.2 |

## 2b. Prior art applied
| Lesson / pattern (prior-art.md) | How this feature applies or improves it |
|---|---|
| PA-1 gap "session lifetime handling not documented" | Explicit, tested make-before-break with drain and dedupe; documented in architecture.md and troubleshooting.md |
| PA-1 L4 serialize audio writes | One sender task per stage writes to the *active* session pointer; the swap is a single assignment |

## 3. Design
`ManagedSttSession` (stt/session.py) is restructured around three long-lived tasks per stage plus one receiver per live session:

```
sender ── reads chunks queue ──▶ self._active (SttSession)          [single writer]
timer  ── after rotate_seconds ─▶ rotate_requested.set()
receiver(session) ── events ──▶ dedupe ──▶ emit(Segment)             [one per session]
                    GoAway ────▶ rotate_requested.set()
rotator ── on rotate_requested: open next (backoff retries, current keeps running)
           → state ROTATING → swap self._active → new receiver → old: audio_stream_end,
             drain ROTATION_DRAIN_SECONDS, close → state LIVE → stats.rotations += 1
```
- `seq` is owned by the manager (not per session); the old session's late finals get the current seq semantics: a late final consumes the next seq unless dropped as a duplicate.
- Dedupe: `deque[(normalized_text, wall)]` of the last 20 finals; a final whose normalized text (lower-case, punctuation-stripped) equals an entry within `DEDUPE_WINDOW_SECONDS` is dropped and counted.
- Gap: `last_rotation_gap_ms` = audio position (bytes sent ÷ 32) at the first partial/final of the new session minus the audio position at the last final of the old session before the swap; exposed in the snapshot and the metrics event.
- Backlog: `StageRunner` starts the source pump only after the first `LIVE` for file sources (`is_local_file`); for streams, the queue becomes a "drop-oldest" queue (custom put that discards the oldest chunk when full) with a `chunks_dropped` counter in the snapshot.
- Settings: `ROTATION_DRAIN_SECONDS` (3.0), `DEDUPE_WINDOW_SECONDS` (5.0).
- Smoke: `lenguaraz smoke-stt --rotate N` forces the rotation timer to N seconds and reports rotations, lost sentences and the gap per rotation.

## 4. Contracts
- `MetricsEvent` unchanged (`rotations`, `errors`); snapshot adds `duplicates_dropped`, `last_rotation_gap_ms`, `chunks_dropped`.
- Status events during rotation: `ROTATING` (detail `"rotating: opening next session"` / `"server GoAway (Ns left)"`) then `LIVE`.

## 5. Dependencies added (justify each)
| Package | Version | License (SPDX) | Allowed per Art. XVII.B? | Why |
|---|---|---|---|---|
| — | — | — | — | none |

## 6. Risks & mitigations
| Risk | Likelihood | Mitigation |
|---|---|---|
| Two sessions per stage briefly exceed the project's concurrent Live session limit | Medium | Overlap ≤ 3 s; documented in scaling docs (plan N stages + 1); on open failure the current session keeps running |
| Late finals of the old session interleave with the new session's captions | Medium | seq assigned at emit time; dedupe on normalized text; the client already ignores stale interims |
| Restructuring regresses 001 behaviour | Medium | Existing `test_stt_session.py` and `test_vad.py` must stay green; new tests are additive |

## 7. Verification strategy
Scripted sessions (`ScriptedSttEngine` with delays) for AC-1…3; runner tests for AC-4/5; real forced-rotation smoke for AC-6; docs-check for AC-7.
