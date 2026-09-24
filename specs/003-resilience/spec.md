# Spec 003 — resilience

**Status:** Approved · **Owner:** human · **Author:** agent · **Created:** 2026-09-24T21:03Z
**Constitution:** v1.0.0 · **Backlog row:** product.md §6 #003

## 1. Why
Live transcription sessions live about ten minutes (GT-2.5, GT-5.1). A conference talk lasts
forty. Feature 001 already reconnects after a `GoAway`, a timer or an error, with backoff and
visible states, but a plain reconnect leaves a gap of one to three seconds in which speech is
not transcribed and the last finals of the old session can be lost. This feature makes the
rotation **make-before-break**: the next session is opened while the current one still
listens, the audio feed switches only when the new session is ready, the old session drains
its last finals, and duplicates are removed. It also stops the connect-time backlog burst that
delays the first captions. It moves **Latency** (no caption gap) and **Quality/Operation**
(nothing lost during a 40-minute talk). Constitution Art. VI [NN].

## 2. User stories
- **US-1 (P0)** As an audience member, I want captions to keep flowing across the ten-minute
  session boundary, so that I never notice that the model connection was replaced.
- **US-2 (P0)** As a production operator, I want zero final captions lost or duplicated at a
  rotation, so that exports and translations are complete and clean.
- **US-3 (P1)** As an operator, I want the first captions of a stage to appear as soon as the
  session is live, not seconds later, so that the start of a talk is not missed.

## 3. Functional requirements
| ID | Requirement | Traces to |
|---|---|---|
| FR-003-01 | **Posta (make-before-break):** on the rotation timer (`SESSION_ROTATE_SECONDS`) or on the server's `GoAway`, the runner MUST open the next Live session while the current one keeps receiving audio; only once the new session is connected MUST the audio feed switch to it. If opening the new session fails, the current session MUST keep running and the attempt MUST be retried with backoff until it succeeds or the current session ends (then the 001 reconnect path applies). | Art. VI.1, US-1 |
| FR-003-02 | **Drain:** after the switch, the old session MUST receive `audio_stream_end` and stay open for `ROTATION_DRAIN_SECONDS` (default 3) so that its pending final captions are still emitted; then it MUST be closed. | Art. VI.1, US-2 |
| FR-003-03 | **Dedupe:** a final caption from the old session whose normalized text matches a final already emitted in the last `DEDUPE_WINDOW_SECONDS` (default 5) MUST be dropped; `seq` MUST keep increasing monotonically across sessions; every interim of an utterance MUST keep the `seq` of its final. | Art. VI.1, US-2 |
| FR-003-04 | **Gap budget:** the caption gap at a rotation (last final of the old session → first partial of the new session, measured on the audio timeline with the sample boundaries) MUST be ≤ 1 s, and no final MUST be lost, on a forced rotation every 20 s over the bundled samples. | Art. V table, AC-2 |
| FR-003-05 | **No backlog burst:** for file sources, audio replay MUST start only when the first session is connected; for live sources, the ingest queue MUST drop the oldest chunks when full so at most 5 s of backlog is sent after a reconnect, and the drop count MUST be visible in the stage snapshot. | US-3 |
| FR-003-06 | **Observability:** the stage snapshot and the `metrics` event MUST expose `rotations`, `errors`, `duplicates_dropped` and `last_rotation_gap_ms`; every rotation MUST be logged with the old and new `session_id`. | Art. VI.3, Art. XI.2 |
| FR-003-07 | **States:** the stage MUST show `ROTATING` from the moment the next session is being opened until the audio feed has switched, then `LIVE`; the 001 semantics of `DEGRADED` (transient failure, retrying) and `STOPPED` (gave up / source ended / stopped by operator) are unchanged. | Art. VI.3 |
| FR-003-08 | **Docs-as-you-go:** `docs/configuration.md` (new keys), `docs/architecture.md` (Posta), `docs/troubleshooting.md` (rotation symptoms) MUST be updated. | Art. XVII.D.6 |

## 4. Non-functional requirements
| ID | Requirement | Measure |
|---|---|---|
| NFR-003-01 | Rotation caption gap | ≤ 1 s p95 over ≥ 3 forced rotations, `make smoke-stt SMOKE_ARGS="--rotate 20"` |
| NFR-003-02 | Lost finals at rotation | 0 over the same run (all sample sentences present) |
| NFR-003-03 | Extra cost of the overlap | ≤ 2 × `ROTATION_DRAIN_SECONDS` of double audio per rotation (documented in cost.md) |

## 5. Acceptance criteria (executable)
- **AC-1** Given a scripted session that emits a final, then `GoAway`, then (while draining) a late final, and a second scripted session that emits a final, when the runner rotates, then the bus receives all three finals in order with strictly increasing `seq`, the late final is not lost, and the states pass `LIVE → ROTATING → LIVE` — verified by `pytest tests/test_rotation.py`
- **AC-2** Given the old session re-emits a final identical to one already published within 5 s, when it arrives, then it is dropped and `duplicates_dropped` increments — verified by `pytest tests/test_rotation.py::test_dedupe`
- **AC-3** Given opening the next session fails twice, when the timer fires, then the current session keeps emitting captions, the stage shows `ROTATING` with a retry detail, and the third attempt switches — verified by `pytest tests/test_rotation.py::test_open_failure_keeps_old_session`
- **AC-4** Given a file source and a session that takes 400 ms to connect, when the stage starts, then no audio chunk is sent before the session is connected and the first chunk's audio position is 0 — verified by `pytest tests/test_runner.py::test_file_source_waits_for_live`
- **AC-5** Given a live (non-file) source and a stalled session, when the ingest queue fills, then the oldest chunks are dropped and `chunks_dropped` is reported — verified by `pytest tests/test_runner.py::test_live_source_drops_oldest`
- **AC-6** Given the EN and ES samples, when `make smoke-stt SMOKE_ARGS="--rotate 20"` runs with the real engine, then ≥ 2 rotations happen, all sentences produce a final, and the measured rotation gap p95 ≤ 1 s — verified by the smoke output (human confirms quota)
- **AC-7** Docs updated and `make docs-check` green — verified by `make docs-check`

## 6. Out of scope
- Session resumption handles / context-window compression (GT-5.3): rotation must not depend on them.
- Redis-backed multi-worker failover (005).
- Admin actions (start/stop from the UI, 004).

## 7. Open questions
- [x] Q1 Drain length 3 s vs 5 s? (default 3 s: finals after `audio_stream_end` arrive within ~0.5 s in our measurements) → default applied
- [x] Q2 Forced-rotation interval for the smoke: 20 s (three rotations on the 55 s sample) → default applied

## Changelog
- 2026-09-24T21:03Z created; Status Approved (non-blocking defaults, HUMAN_INBOX S3-1).
