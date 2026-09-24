---
description: Create or update a feature spec (SDD step 1-2)
argument-hint: <feature number, e.g. 001>
---
Feature: $ARGUMENTS (see .specify/memory/product.md §6).
1. `date -u`; check the milestone clock.
2. Create `specs/$ARGUMENTS-<name>/spec.md` from `.specify/templates/spec-template.md`. What and why only; no implementation details. Every FR traces to an MVP gate, a user story or a judging criterion. Acceptance criteria in Given/When/Then with the command that verifies each.
3. List open questions. Resolve with ground truth / Gemini Docs MCP what you can; batch the rest to me per CLAUDE.md §5 with recommended defaults.
4. Set Status: Approved once I confirm or defaults apply. Commit `docs(spec): NNN <name>`.
Timebox: 15 minutes.
