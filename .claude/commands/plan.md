---
description: Create the technical plan with the constitution gate (SDD step 3)
argument-hint: <feature number>
---
Feature: $ARGUMENTS.
1. Read the approved spec. Create `plan.md` from the template.
2. Fill the Constitution check. Any ❌ must be resolved in the design or escalated; do not proceed with a ❌.
3. For EVERY Gemini API surface used, call the Gemini Docs MCP `search_documentation` and record the reference in "Verified references". Follow the gemini-live-api-dev / gemini-api-dev skills. Never invent fields.
4. Contracts, dependencies (justified), risks, verification strategy.
5. Commit `docs(plan): NNN <name>`. Timebox: 15 minutes.
