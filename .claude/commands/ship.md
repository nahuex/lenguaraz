---
description: Final submission preparation (M6-M7)
---
1. `date -u`; enforce code freeze at 2026-09-25T13:00:00Z.
2. Run `make mvp-check`, `make verify`, `make license-check`, `make spdx-check`, `make docs-check`, `make fresh-clone-test` (against the public GitHub URL), full gitleaks history scan. Fix only blockers.
3. Finalize README.md + README.es.md per CLAUDE.md §9 using only measured numbers from docs/metrics.md.
4. Generate `docs/video-script.md` (1:30–1:50, beats with timestamps), the stages.yaml for recording, and after I record, export the EN SRT from Lenguaraz for YouTube.
5. Draft `docs/devpost.md` (Inspiration, What it does, How we built it, Challenges, Accomplishments, What we learned, What's next; one line per judging criterion with evidence; links placeholders).
6. Checklist for me: repo public, GitHub shows Apache-2.0, NOTICE and THIRD_PARTY_LICENSES.md present, deploy docs complete, video public on YouTube with EN subs, Devpost submitted before 13:00Z, Nerdearla registration done. Tag v1.0.0 after my confirmation.
