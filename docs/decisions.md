# Decisions log

Short ADR-style entries (1–3 lines each). Newest at the bottom.

- **2026-09-24T15:20Z · D-000-1 Reuse the pre-existing repo.** The owner had already created `nahuex/lenguaraz` (empty, created 15:04Z inside the build window) before H0. Instead of `gh repo create`, T-000 initializes locally and adds it as `origin` over SSH; visibility is flipped to public in T-000 (Constitution Art. I.4).
- **2026-09-24T15:20Z · D-000-2 Narrow the `.env` deny rule.** The materialized `.claude/settings.json` denied `Read(./.env.*)`, which also blocks `.env.example` (a committed placeholder file the agent must maintain). Owner approved narrowing it to `Read(./.env)` + `Read(./.env.local)` at H0. The agent's own permission classifier refuses to edit its settings, so the owner applies the one-line change.
- **2026-09-24T15:25Z · D-000-3 Ground-truth re-verification without the MCP.** The Gemini Docs MCP only loads after the restart at the end of PHASE 3. GT-2..GT-8 and GT-10 were re-verified against the official pages on ai.google.dev with independent fetch agents plus an adversarial re-fetch for every claim graded as drifted or unverifiable. Plans still cite the MCP `search_documentation` for every API surface once it is available.
