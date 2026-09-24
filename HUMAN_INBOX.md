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
| T0-2 | 2026-09-24T15:48Z | Fix `.claude/settings.json` deny list: the two `Read(...)` lines must be exactly `"Read(./.env)",` and `"Read(./.env.local)",` (owner's edit replaced the wrong line and left `Read(./.env.*)`) | Apply before the restart | — | open |
