# HUMAN INBOX

| ID | UTC | Question | Recommended default | Answer | Status |
|---|---|---|---|---|---|
| H0-1 | 2026-09-24T15:15Z | Copyright holder for LICENSE/NOTICE | "Copyright 2026 <full name>" | "OK" (twice) without a name → agent wrote "Nahuel Cortes" (derived from the owner's git identity). Owner to confirm exact spelling / accents / second surname | answered (confirm spelling) |
| H0-2 | 2026-09-24T15:15Z | Create public repo `lenguaraz` with gh? | yes | Repo created by owner and set to public by owner at ~15:33Z; used as origin over SSH. Commits authored as `Nahuel Cortes <95323261+nahuex@users.noreply.github.com>` | answered |
| H0-3 | 2026-09-24T15:15Z | Paste GEMINI_API_KEY into `.env` and reply OK | — | Blocked: `.env.example`/`.env` cannot be created until the settings deny list reads `Read(./.env)` + `Read(./.env.local)` (see T0-2). Then agent creates both files and owner pastes the key | open |
| H0-4 | 2026-09-24T15:15Z | Concurrent Live session limit seen in AI Studio | Assume Tier 1; demo with 2–4 real stages | OK (default applies; GT-7.3: the public rate-limits page publishes no figure) | answered |
| H0-5 | 2026-09-24T15:15Z | Conference palette (hex) | Neutral accessible dark theme | OK (default applies) | answered |
| H0-6 | 2026-09-24T15:15Z | Two Nerdearla talks for the demo (EN technical + ES) | Choose together at H4 | OK (default applies) | answered |
| T0-1 | 2026-09-24T15:25Z | Install make, gitleaks, Gemini Docs MCP and the two Gemini skills (agent is not allowed to install them) | Run the winget/npx commands before the restart | Owner ran them at ~15:45Z (make 4.4.1 and gitleaks 8.30.1 verified; MCP + skills verified after restart) | answered |
| T0-2 | 2026-09-24T15:48Z | Fix `.claude/settings.json` deny list: the two `Read(...)` lines must be exactly `"Read(./.env)",` and `"Read(./.env.local)",` (owner's edit replaced the wrong line and left `Read(./.env.*)`) | Apply before the restart | Fixed by owner at ~15:52Z; `.env.example` and `.env` created at 15:56Z | answered |
| T0-3 | 2026-09-24T15:56Z | The `gemini-live-api-dev` / `gemini-api-dev` skills do not appear in the agent's skill list after the restart (the Gemini Docs MCP does) | Non-blocking: ground truth + MCP cover the API surface; re-run `npx skills add google-gemini/gemini-skills --skill gemini-live-api-dev --global` and `--skill gemini-api-dev --global` in a terminal and restart when convenient | — | open |
| S1-1 | 2026-09-24T16:02Z | Spec 001 Q1: default `STT_MODE` | `SMART` (cleaner captions; per-stage override) | default applied | answered by default |
| S1-2 | 2026-09-24T16:02Z | Spec 001 Q2: sample clip topics (EN: Kubernetes/eBPF/observability · ES: Python asyncio/Docker/despliegue), original scripts | yes | default applied | answered by default |
| S2-1 | 2026-09-24T16:02Z | Spec 002 Q2: progressive translation on by default (flag; first cut if behind) | on | default applied | answered by default |
