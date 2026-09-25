# Plan 005 — scale-proof

**Spec:** specs/005-scale-proof/spec.md (Approved) · **Created:** 2026-09-24T21:34Z

## 1. Constitution check
| Article | Status | Note |
|---|---|---|
| I Compliance | ✅ | Demonstrates "5, 10 or more stages"; report is honest about real vs simulated (Art. XIV) |
| II Google terms | ✅ | Real stages use the same server-side key |
| III SDD traceability | ✅ | Tasks reference FR-005-xx |
| IV Docs-verified | ✅ | No new API surface; pricing from GT-6 |
| V Performance budgets | ✅ | Percentiles from the same `latency_ms` definitions as the runtime |
| VI Resilience | ✅ | Uses `StageManager`; a failing real stage does not stop the run |
| VII Scale & cost | ✅ | This feature is Art. VII.4 |
| VIII Security | ✅ | No new endpoints |
| IX Privacy | ✅ | Nothing persisted except the report |
| XI Operability | ✅ | `make simulate`; report linked from docs |
| XII Tests | ✅ | Fake-only run in the suite |
| XIII Simplicity | ✅ | Reuses runner, bus, engines; `psutil` only for CPU/RSS (falls back to n/a) |
| XVII Open source | ✅ | `psutil` is BSD-3-Clause (allowed); SPDX headers |

## 2. Verified references
| API surface used | Verified via | URL | GT |
|---|---|---|---|
| Pricing | GT re-verified at T-000 | ai.google.dev/gemini-api/docs/pricing | GT-6 |

## 3. Design
- `lenguaraz/tools/simulate.py`: builds N `StageConfig`s from the two bundled samples (alternating EN/ES, `loop: true`, `targets` = the other language), a `MixedSttEngine`/`MixedTranslationEngine` that route the first K stage ids to the Gemini engines and the rest to the fakes, a `StageManager` with `metrics_interval=1`, one bus listener per language per stage that counts events and collects `latency_ms` by kind (commit delay for finals of the source language; translation latency for translated finals), a sampler task (`psutil.Process().cpu_percent()`, `memory_info().rss`) every second, and a `Report` dataclass rendered to Markdown and JSON.
- Cost: sum of `est_cost_usd` of real stages ÷ (real stages × duration) × 3600 → cost per stage-hour; fake stages contribute nothing (stated).
- CLI: `lenguaraz simulate`; Makefile `simulate` with `SIM_ARGS`.
- **Viewer fan-out load test (follow-up, FR-005-05)** — `lenguaraz/tools/loadtest.py`: starts
  `lenguaraz serve` as a subprocess (`ENGINE=fake`, `WS_MAX_CONN_PER_IP=1000000`,
  `LOG_LEVEL=WARNING`, `STAGES_FILE`), waits for `/healthz`, then for every step in
  `--viewers` (default `100,500,1000`) opens that many `websockets` clients on
  `ws://127.0.0.1:<port>/ws/<stage>?lang=<source>` (round-robin over the first `--stages`
  stages), holds them for `--seconds` and records the receive time of every caption per
  viewer. Fan-out spread = last − first receipt of the same event (identity: stage, lang,
  `seq`, `is_final`, text), p50/p95/max over the events that every connected viewer of that
  (stage, lang) received; also events per viewer (min/median), connected/failed/dropped
  viewers, server CPU avg/max and RSS delta sampled by `psutil` on the *real* interpreter
  (the Windows venv `python.exe` is a launcher, so the deepest descendant is the server) and
  the client process CPU. Writes `docs/loadtest-report.md` + `.json` and upserts the
  `## Viewer fan-out` section of `docs/scale-report.md`, which `simulate.write_report`
  preserves. Stop = `CTRL_BREAK_EVENT` (uvicorn handles `SIGBREAK`) or `SIGTERM`, then
  terminate/kill of the launcher and its descendants. CLI `lenguaraz loadtest`; Makefile
  `loadtest` with `LOAD_ARGS`.

## 4. Contracts
`docs/scale-report.md` sections: Summary table, Per-stage table, Method and honesty note. JSON mirrors the dataclass.

## 5. Dependencies added
| Package | Version | License | Allowed | Why |
|---|---|---|---|---|
| psutil | latest, pinned | BSD-3-Clause | ✅ | Process CPU and RSS in the simulator (optional at runtime) |
| websockets | `>=13` (16.1.1 locked; already a transitive dependency of `google-genai` and `uvicorn[standard]`) | BSD-3-Clause | ✅ | WebSocket client for the viewer fan-out load test (`lenguaraz loadtest`) |

## 6. Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Tier 1 concurrent session cap with many real stages | Medium | Default `--real 2`; the owner reads the limit in AI Studio before raising it (H3) |
| CPU numbers are laptop-specific | High | Report records machine info (CPU count, platform) and states it |

## 7. Verification
`pytest tests/test_simulate.py` (fake), `make simulate` (mixed, H3), `make docs-check`;
`pytest tests/test_loadtest.py` (pure parts + 20 viewers for 2 s against a subprocess fake
server), `make loadtest LOAD_ARGS="--viewers 100,500,1000 --seconds 30"` (no quota).
