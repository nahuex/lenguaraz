# STATE

- Now (UTC): 2026-09-24T21:23Z — Window opened 2026-09-24T15:00:00Z
- Current milestone: **M3 Unbreakable** (deadline 22:30Z) — feature 003 built and proven with forced rotations on the real engine (EN 1 rotation / ES 2 rotations: 7/7 finals, 0 lost, 0 duplicates, WER unchanged 3.2 % / 4.3 %). M2 exit (H2 + `v0.1.0`) still waits for the owner; M1 exit (H1) too.
- Done: features 001 (17 tasks) and 002 (8 of 10 tasks; H2 + converge pending) · Devpost rules re-check applied · 003 T-01…05 (make-before-break Posta with pause-aligned switch, drain, dedupe, seq across sessions, no backlog burst for files, drop-oldest for streams, `smoke-stt --rotate`, docs) · `make verify` green (~140 tests) · `make mvp-check` 7/7 PASS (fake and real)
- In progress: commit 003 · T-003-06 converge
- Next 3: 004 operations with **Acta (SRT/VTT/TXT export) first**, then Mangrullo status table, then Pizarrón overlay (QR and glossary UI cut) · 005 simulator + scale report (RedisBus cut) · 006 auto-glossary · then 007 CI/hardening and 008 docs for M5/M6
- Risks: owner checkpoints pending (H1, H2, eligibility E1, naming N1) — the tag `v0.1.0` cannot be created without H2 · M4 (25 03:00Z) needs 004+005+006 in ~5.5 h · rotation measurements: `last_rotation_gap_ms` includes the natural pause between sentences (documented); the audience-relevant number is the first partial of the sentence after the switch (0.8–2.7 s in two runs) · interim count per run varies a lot server-side (6–80 per 50 s)
- Cuts applied: 011, 010, 009, RedisBus (005), QR codes + cosmetic UI, glossary editing UI
