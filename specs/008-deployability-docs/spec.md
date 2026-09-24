# Spec 008 — deployability docs & submission

**Status:** Shipped · **Owner:** human · **Author:** agent · **Created:** 2026-09-24T22:16Z
**Constitution:** v1.0.0 · **Backlog row:** product.md §6 #008

## 1. Why
The judges' Deployment & Operation criterion and Art. XVII.D ask that **any conference** can
deploy Lenguaraz from the public repo without us. Features 001–007 documented as they went;
008 completes the required set, mirrors the entry points in Spanish, proves the docs with a
fresh-clone test, and prepares the submission material (Devpost text, video script, EN SRT).

## 2. User stories
- **US-1 (P0)** As a volunteer tech lead at an unknown conference, I want to go from the repo
  to live captions on a VM with TLS in one afternoon, so that I never need the authors.
- **US-2 (P0)** As the same person, I want copy-paste recipes for the audio I already have
  (OBS, vMix, HLS, SRT, a file), so that plugging Lenguaraz in takes minutes.
- **US-3 (P1)** As a Spanish-speaking organizer, I want the README and quickstart in Spanish.
- **US-4 (P1)** As a maintainer, I want `make fresh-clone-test` to prove the quickstart works
  from a clean clone in dry-run mode, so that docs never rot silently.
- **US-5 (P1)** As the owner, I want the event name, colors and logo to be configuration, so
  that the audience pages carry the conference's identity without touching code.

## 3. Functional requirements
| ID | Requirement | Traces to |
|---|---|---|
| FR-008-01 | The Art. XVII.D.3 documentation set MUST exist and answer the listed questions: `docs/deploy/{quickstart,production,scaling,audio-sources,cloud-run}.md`, `docs/{configuration,customization,cost,architecture,security,privacy,troubleshooting}.md`, `docs/operations/runbook.md`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `README.md`, `README.es.md`, `docs/es/quickstart.md`, `examples/{stages.minimal.yaml,stages.multitrack.yaml,branding.example.yaml}` and `.env` profiles under `examples/env/`. `make docs-check` MUST fail when any is missing. | US-1..3, Art. XVII.D.3 |
| FR-008-02 | `make fresh-clone-test` MUST clone the public repository into an empty temporary directory, follow the quickstart in dry-run mode (Docker Compose when Docker is available, otherwise the developer path), wait for `/healthz` to report `ok` with `engine=fake`, confirm captions flowed (transcript export of a stage is non-empty), and clean up. | US-4, Art. XVII.D.5 |
| FR-008-03 | Branding MUST be runtime configuration: `BRANDING_FILE` (default `branding.yaml`, optional) with `event_name`, `tagline`, `primary_color`, `logo_url`, `footer`; served at `GET /api/branding` and applied by the audience pages (header name/logo, accent color). No brand asset is committed; `branding/local/` stays git-ignored. | US-5, Art. XVII.C |
| FR-008-04 | README (EN) MUST add: docs index with links to every file of FR-008-01, license badge, **Prior art & acknowledgments** (PA-1..PA-4 from `.specify/memory/prior-art.md`, lessons adopted, no code copied), "How we built it" (SDD + loop, link to the constitution), limitations, and a screenshot placeholder the owner fills at H4. `README.es.md` mirrors it in Spanish. | Art. XVII.D.3, DoD |
| FR-008-05 | Submission material: `docs/devpost.md` (title, tagline, inspiration, what it does, how we built it, challenges, accomplishments, what we learned, what's next, built with, links), `docs/video-script.md` (1–2 min shot list with timings and on-screen text) and the procedure to export the EN SRT of the demo from Acta. | H4, H5 |
| FR-008-06 | Docs MUST be event-agnostic (no conference name as a default, no brand assets), every command copy-pasteable; outdated statements from earlier features ("lands in feature 003", "feature 008") MUST be removed. | Art. XVII.D.2/4 |

## 4. Non-functional requirements
| ID | Requirement | Measure |
|---|---|---|
| NFR-008-01 | Fresh-clone test wall time | ≤ 6 min with Docker (image build), ≤ 3 min developer path |
| NFR-008-02 | Reading time of the quickstart | ≤ 15 min to first captions (Art. XVII.D.3) |

## 5. Acceptance criteria (executable)
- **AC-1** `make docs-check` passes and fails when a required doc is renamed — verified by `pytest tests/test_docs_check.py`
- **AC-2** `make fresh-clone-test` exits 0 on the public repo and prints the healthz payload and the number of transcript lines — verified by running it (H3 watches it)
- **AC-3** `GET /api/branding` returns the defaults without a file and the file's values with one; the Fogón header shows `event_name` — verified by `pytest tests/test_branding.py` and vitest
- **AC-4** README EN/ES contain the FR-008-04 sections — verified by `make docs-check` (section headings list)
- **AC-5** `docs/devpost.md` and `docs/video-script.md` exist — verified by `make docs-check`

## 6. Out of scope
GIF/screenshot capture (owner at H4), Spanish mirrors of every doc (only README and quickstart).

## 7. Open questions
- [x] Q1 Fresh-clone test transport: prefer Docker when present? → yes, fallback to the developer path.

## Changelog
- 2026-09-24T22:16Z created; Status Approved (defaults applied).
