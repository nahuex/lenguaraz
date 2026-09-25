# Contributing to Lenguaraz

Thanks for helping. Lenguaraz is Apache-2.0, built for any conference to deploy, and run by
a small set of rules that keep it that way. This page has everything you need to set up, make
a change and get it merged. Behaviour expectations are in [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md);
security problems go through [`SECURITY.md`](SECURITY.md), not public issues.

## Set up

Requirements: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 24, ffmpeg on the PATH
(only for non-WAV sources), Docker optional.

```bash
git clone https://github.com/nahuex/lenguaraz.git && cd lenguaraz
uv sync                # Python environment incl. the dev group (pytest, ruff, mypy, ...)
make web               # build the audience view into web/dist (npm ci + vite build)
make hooks             # pre-commit hook: gitleaks secrets scan + SPDX header check
ENGINE=fake make dev   # http://127.0.0.1:8000 with auto-reload, no credentials needed
```

`ENGINE=fake` replays the reference transcripts next to the bundled samples through the whole
pipeline (bus, translation fan-out, WebSocket, pages) without calling Google. For the
frontend alone: `cd web && npm run dev` (Vite on port 5173) and `npm test` (vitest).

## How work is organized: spec-driven development

Every feature lives in `specs/NNN-name/` and goes through four documents, in order:
`spec.md` (what and why, requirements with ids `FR-NNN-xx`, acceptance criteria) → `plan.md`
(how, a constitution check and the verified API references) → `tasks.md` (ordered tasks
`T-NNN-xx`, each with a verify command) → the implementation loop, one task at a time. The
[constitution](.specify/memory/constitution.md) is the supreme law of the repo; verified
Gemini API facts are in `.specify/memory/ground-truth.md` and nothing may contradict them.
Small fixes do not need a new spec: add a task line to the relevant feature.

Every Gemini API field or model id used in code must be verified against the official docs
and cited in the plan. Model ids are configuration (`GEMINI_*_MODEL`), never literals in logic.

## Commits and the verify gate

Conventional Commits with the task id in brackets:

```
feat(stt): rotate the Live session on GoAway without losing finals [T-003-02]
fix(export): clamp overlapping cue times in SRT [T-004-07]
docs(configuration): document VAD_THRESHOLD [T-001-17]
```

`make verify` must be green before every commit. It runs `ruff check` and `ruff format
--check`, `mypy`, `pytest`, the frontend build and `make spdx-check`. Never make it green by
weakening an assertion; if a spec changed, change the spec first (with a changelog line).

## Tests never spend quota

Tests run with `ENGINE=fake` and cannot reach Google: `tests/conftest.py` installs a
`no_network` guard that fails any socket connection to a non-local host. Use the fakes:
`FakeSttEngine` / `FakeSttSession` (`lenguaraz/stt/fake.py`), `FakeTranslator`
(`lenguaraz/translate/fake.py`), `FakeAutoGlossary` (`lenguaraz/glossary/auto.py`) and the
scripted `FakeLiveSession` in `tests/test_stt_gemini.py` for interim/final/`GoAway`/error
sequences. Every bug fix starts with a failing test that reproduces it.

Real-API checks are explicit and cost a little money; run them only with your own key in `.env`:

```bash
make smoke-stt                                   # WER, first-partial and utterance-to-final latency, tokens
make smoke-stt SMOKE_ARGS="--sample samples/es_asyncio.wav --rotate 60 --glossary auto"
make smoke-translate                             # EN->ES and ES->EN, time-to-first-token, glossary adherence
make mvp-check MVP_ARGS="--engine gemini"        # the seven MVP gates on the real engine
make simulate SIM_ARGS="--stages 10 --seconds 60 --real 2"   # scale report (docs/scale-report.md)
```

Record measured numbers in `docs/metrics.md` with the date and method; the README states
only what was measured.

## Dependencies and licenses

Before adding a Python or npm package, check its license against the allowlist enforced by
`make license-check` (Apache-2.0, MIT, MIT-0, BSD-2/3-Clause, ISC, 0BSD, Zlib, PSF-2.0,
Python-2.0, MPL-2.0, OFL-1.1, Unlicense). GPL/AGPL/SSPL/BUSL and "non-commercial" licenses
are rejected; LGPL needs explicit owner approval. Name the dependency and its license in the
feature `plan.md`, then run `make license-check` and commit the regenerated
`THIRD_PARTY_LICENSES.md` (CI fails if it is stale). External programs (ffmpeg, Redis) are
called as separate processes, never vendored.

## Source headers and docs-as-you-go

Every `.py`, `.ts`, `.tsx`, `.js`, `.css`, `.yml`, `.yaml`, `.sh`, `Dockerfile` and `Makefile`
starts with `SPDX-License-Identifier: Apache-2.0` in that language's comment syntax
(`make spdx-check`; Markdown files carry no header). Docs ship in the same commit series as
the code: a new setting goes into `docs/configuration.md` (its env table is compared with
`Settings` by `make docs-check`), a new endpoint into `docs/architecture.md`, a new failure
mode into `docs/troubleshooting.md` or the runbook. Docs are event-agnostic: no conference
name, stage, language or brand as a default.

## Components

The product is called Lenguaraz; every component carries the standard name used by
live-captioning platforms, in the UI, the routes, the docs and the code.

| Component | Code | Role |
|---|---|---|
| Audio ingest | `lenguaraz/ingest/` | Audio in (ffmpeg / WAV reader) |
| Transcription | `lenguaraz/stt/` | Live transcription; `stt/session.py` owns the make-before-break session rotation |
| Translation | `lenguaraz/translate/` | Translation fan-out; `translate/demand.py` decides which languages are active (language demand) |
| Event bus | `lenguaraz/bus/` | Fan-out to the audience |
| Glossary | `lenguaraz/glossary/` | Glossary and auto-glossary |
| Transcript export | `lenguaraz/export.py` | SRT/VTT/TXT export |
| Live captions page | `web/src/pages/LiveCaptions.tsx`, route `/live/{stage}` | Audience view |
| Overlay | `web/src/pages/Overlay.tsx`, route `/overlay/{stage}` | OBS/vMix browser source |
| Admin | `web/src/pages/Admin.tsx`, `lenguaraz/api/admin.py`, route `/admin` | Operator dashboard |

Routes are `/live/{stage}`, `/overlay/{stage}` and `/admin`; the caption WebSocket is
`/ws/{stage}` and the JSON API lives under `/api/`. Stage ids are ASCII.

## UI components

The web pages are built on [shadcn/ui](https://ui.shadcn.com) primitives (MIT, Radix-based)
copied into `web/src/components/ui/`. Compose those (`Button`, `Card`, `Badge`, `RadioGroup`,
`ToggleGroup`, `Switch`, `Table`, `Input`, `Label`, `Alert`, `Skeleton`, `Separator`) and
`lucide-react` icons; do not hand-roll buttons, inputs or toggles with raw Tailwind, and do
not hardcode colours: use the tokens in `web/src/index.css` (see the Theming section of
[`docs/customization.md`](docs/customization.md#theming)). A missing primitive is added with
`npx shadcn@latest add <name>` inside `web/`, then gets the SPDX line and the shadcn
attribution comment on top. Every control keeps keyboard operation, a visible focus ring and
an accessible name; `web/src/test/a11y.test.tsx` runs axe on the shared components and the
Overlay page (`web/src/pages/Overlay.tsx`, `overlay.css`) stays on its own transparent CSS.

## Proposing changes

- **Issues** for bugs (steps, expected vs actual, engine and version from `/healthz`) and for
  ideas; say which spec or requirement they touch if you know.
- **Pull requests**: small, one task or fix each, `make verify` green, tests included, docs
  updated, a line in [`CHANGELOG.md`](CHANGELOG.md) under `[Unreleased]`. Link the issue or
  spec. Anything that changes an API surface with Gemini needs the doc reference in the plan.
- The owner reviews; changes to the constitution or to the license policy need explicit
  owner approval.

## Licensing of contributions

Lenguaraz is licensed under the Apache License 2.0 ([`LICENSE`](LICENSE)). By submitting a
contribution you agree that it is licensed under the same terms, as described in Section 5
of the license ("Submission of Contributions"), with no additional terms. A
`Signed-off-by:` line (`git commit -s`, the Developer Certificate of Origin) is welcome as a
statement that you have the right to submit the work; CI does not enforce it. Do not
contribute code copied from other subtitle or translation projects, third-party media,
logos or fonts without a compatible license.
