# STATE

- Now (UTC): 2026-09-24T16:05Z — Window opened 2026-09-24T15:00:00Z (first session started 15:07Z)
- Current milestone: **M0 Kickoff closed at 16:00Z** (20 min late: NOTICE/identity round-trip + settings fix). Next: M1 First words (deadline 18:30Z) — a sample file flows ffmpeg → STT → WS → browser, one stage, interim + final
- Done: PHASE 1 tooling · PHASE 2 governance · H0 · T-000 bootstrap (`06ef354`, `95927fe`, `8a99bee`; public repo, GitHub reports Apache-2.0) · restart done: Gemini Docs MCP loaded and working (`gemini_search_docs` / `gemini_get_doc`) · `.env.example` + `.env` created (owner pastes GEMINI_API_KEY) · ground truth re-verified (no drift) · **spec 001 core-pipeline Approved (`e2c97bb`)** · **spec 002 translation Approved (`b6d6887`)** — open questions resolved with non-blocking defaults (HUMAN_INBOX S1-1, S1-2, S2-1)
- In progress: /plan 001 (constitution gate + MCP-verified references)
- Next 3: /plan 001 · /tasks 001 · /loop 001 (target M1 by 18:30Z)
- Risks: GEMINI_API_KEY not yet confirmed in `.env` → `make smoke-stt` and `make samples` wait for the owner's "OK" · gemini skills (`gemini-live-api-dev`, `gemini-api-dev`) not visible in the skill list after restart (non-blocking, T0-3) · NOTICE name "Nahuel Cortes" to be confirmed by owner · M1 budget is 2h25m for config + ingest + STT + bus + WS + minimal UI: plan must keep the first vertical slice thin (fake engine first, real STT smoke as soon as the key is in)
- Cuts applied: none
