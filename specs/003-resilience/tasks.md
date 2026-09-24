# Tasks 003 — resilience

**Plan:** specs/003-resilience/plan.md · Legend: `[P]` parallelizable · `[H]` needs human · each task ≤ 45 min.

| ID | Task | Refs | Verify | Status |
|---|---|---|---|---|
| T-003-01 | Failing tests for make-before-break, drain, dedupe and open-failure (`tests/test_rotation.py`) using scripted sessions with delays | AC-1, AC-2, AC-3 | `uv run pytest tests/test_rotation.py` (red) | ☐ |
| T-003-02 | Restructure `ManagedSttSession`: active-session pointer, rotator task, per-session receivers, drain + close, dedupe deque, seq across sessions, `last_rotation_gap_ms`; settings `ROTATION_DRAIN_SECONDS`, `DEDUPE_WINDOW_SECONDS`; keep 001/VAD tests green | FR-003-01/02/03/06/07 | `uv run pytest tests/test_rotation.py tests/test_stt_session.py tests/test_vad.py` | ☐ |
| T-003-03 | Runner: file sources start after the first `LIVE`; drop-oldest ingest queue for live sources with `chunks_dropped`; snapshot fields; tests | FR-003-05, FR-003-06, AC-4, AC-5 | `uv run pytest tests/test_runner.py` | ☐ |
| T-003-04 [H quota] | `smoke-stt --rotate N`: forced rotation, lost-sentence check, gap per rotation; run on EN and ES with `--rotate 20`; record in `docs/metrics.md` | FR-003-04, AC-6, NFR-003-01/02 | `make smoke-stt SMOKE_ARGS="--rotate 20"` | ☐ |
| T-003-05 | Docs: configuration (new keys), architecture (Posta), troubleshooting (rotation), metrics notes; `make docs-check` | FR-003-08, AC-7 | `make docs-check` | ☐ |
| T-003-06 | Converge: spec vs code, mark Shipped, STATE.md; **M3 exit** | Art. III.3 | `make verify` | ☐ |

## Estimate vs clock
Started 21:05Z; M3 deadline 22:30Z. T-01/02 ≈ 45 min, T-03 ≈ 20 min, T-04 ≈ 10 min, T-05/06 ≈ 10 min. If T-02 is not green by 22:00Z, ship rotation without the backlog change (T-03 moves to 004's converge).

## Definition of Done (feature)
- [ ] All tasks ☑ and all ACs pass
- [ ] `make verify` green
- [ ] Docs updated per Art. XVII.D.6
- [ ] New files carry SPDX headers
- [ ] STATE.md updated
