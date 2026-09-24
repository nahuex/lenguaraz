---
description: Run the implementation loop on the active feature
argument-hint: [feature number] [max tasks, default all]
---
Run THE LOOP from CLAUDE.md §4 on feature $ARGUMENTS, task by task:
ORIENT → SELECT → TRACE → RED → GREEN → VERIFY → EVALUATE → REPAIR(≤3) → COMMIT → RECORD → TIMEBOX.
- `make verify` must be green before each commit.
- Real Gemini calls only in `make smoke-*`, and only after I confirmed quota in H0.
- Every 3 tasks post a 3-line status (done / next / clock).
- Stop and use the human protocol on: 3rd failed repair, any [H] task, any constitution conflict, milestone at risk.
When all tasks are done: converge (spec vs code), mark the spec Shipped, update README section and STATE.md, and propose the next feature.
