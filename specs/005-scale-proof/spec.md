# Spec 005 — scale-proof

**Status:** Shipped (H3 pending) · **Owner:** human · **Author:** agent · **Created:** 2026-09-24T21:33Z
**Constitution:** v1.0.0 · **Backlog row:** product.md §6 #005 (RedisBus half cut by the ladder)

## 1. Why
The challenge asks for "5, 10 or more stages in parallel" and judges **Scalability**: "can it
run many sessions at once without big changes or prohibitive cost?". Constitution Art. VII.4:
scale is demonstrated, not asserted. This feature adds a simulator that runs N stages in one
process — any mix of real Gemini stages and fake ones — and produces a report with captions
per stage, latency percentiles, CPU and memory per stage, and cost per stage-hour computed
from measured usage. The report feeds the README, `docs/cost.md` and `docs/deploy/scaling.md`.

## 2. User stories
- **US-1 (P0)** As an organizer, I want to see what 10 or 30 stages cost in CPU, memory and
  money before I commit, so that I can size a machine and a budget.
- **US-2 (P1)** As a judge, I want an honest report that states how many stages were real and
  how many simulated, so that I can trust the numbers.

## 3. Functional requirements
| ID | Requirement | Traces to |
|---|---|---|
| FR-005-01 | `lenguaraz simulate --stages N --seconds S [--real K]` MUST run N stages in one process from the bundled samples (looped), K of them with the real Gemini engines and N−K with the fake engines, with one listener per language per stage, for S seconds, then stop cleanly. | US-1, Art. VII.4 |
| FR-005-02 | The report MUST contain: stages (real/fake), duration, finals and partials per stage, translated captions, commit-delay p50/p95 and translation-latency p50/p95 for real stages, CPU average/max and RSS start/end for the process, per-stage CPU and memory deltas, measured cost of the real stages and the derived cost per stage-hour (pricing date), and a sentence stating what was real and what was simulated. | US-1, US-2, Art. VII.3, Art. XIV |
| FR-005-03 | The report MUST be written to `docs/scale-report.md` and `docs/scale-report.json`; `make simulate` MUST run it with defaults (`--stages 10 --seconds 60 --real 2`). | US-1 |
| FR-005-04 | The fake-only path MUST run without credentials or network (usable in tests and CI). | Art. XII.2 |
| FR-005-05 | `lenguaraz loadtest --viewers 100,500,1000 --seconds S [--stages N]` MUST start the server with the fake engine as a subprocess and, per step, open that many WebSocket viewers (round-robin over the first N stages, `lang` = source language), hold them for S seconds and report: connected/failed/dropped viewers, caption events per viewer (min/median), fan-out spread p50/p95/max (wall time between the first and the last viewer receiving the same caption event, over events every viewer of that stage/language received), server CPU avg/max and RSS delta (psutil on the server process), client-process CPU. It MUST write `docs/loadtest-report.md` + `.json`, keep a `## Viewer fan-out` section in `docs/scale-report.md`, and state honestly that the engine is fake and that clients and server share one host over loopback. | US-1, US-2, Art. VII.4, Art. XIV |

## 4. Non-functional requirements
| ID | Requirement | Measure |
|---|---|---|
| NFR-005-01 | 10 fake stages for 60 s on a laptop | CPU average < 30 % of one core, RSS growth < 200 MB (reported, not gated) |
| NFR-005-02 | Fake-only test run | 5 stages × 2 s completes in < 10 s in the test suite |
| NFR-005-03 | Viewer fan-out on a laptop | 1000 viewers on one stage connect without failures and the spread p95 stays < 500 ms (reported, not gated) |

## 5. Acceptance criteria (executable)
- **AC-1** Given `simulate(stages=5, seconds=2, real=0)` in the test suite, when it finishes, then the report has 5 stages, finals > 0 on each, CPU/RSS fields and the honesty sentence "0 real, 5 simulated" — verified by `pytest tests/test_simulate.py`
- **AC-2** Given `make simulate` with `--real 2` and a key, when it finishes, then `docs/scale-report.md` shows real-stage latency percentiles and a cost per stage-hour — verified by the human at H3
- **AC-3** `make docs-check` green after linking the report — verified by `make docs-check`
- **AC-4** Given `run_loadtest(viewers=[20], seconds=2)` in the test suite against a subprocess server with `ENGINE=fake`, when it finishes, then 20/20 viewers connected, every viewer received at least one caption, the spread is computed over complete events and the sampled RSS is the server's (not a launcher stub) — verified by `pytest tests/test_loadtest.py`; the 100/500/1000 run is `make loadtest` and its numbers land in `docs/loadtest-report.md`, `docs/scale-report.md`, `docs/deploy/scaling.md` and `docs/metrics.md`

## 6. Out of scope
- Redis bus and multi-worker locks (ladder cut; documented as the path beyond one machine in `docs/deploy/scaling.md`).
- Load-testing with thousands of *real browsers* on a venue network: the load test (FR-005-05) uses WebSocket clients on the loopback interface of the same host, which the report states.

## 7. Open questions
- [x] Q1 Default `--real 2` (keeps within Tier 1 concurrent sessions) → default applied

## Changelog
- 2026-09-24T21:33Z created; Status Approved.
- 2026-09-25T02:40Z FR-005-05, NFR-005-03, AC-4 added (viewer fan-out load test, `make loadtest`); the "thousands of browsers" out-of-scope item narrowed to real browsers on a venue network. The README's "captions are plain WebSocket events" now has a measured number behind it.
