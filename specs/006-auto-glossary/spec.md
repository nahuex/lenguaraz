# Spec 006 — auto-glossary

**Status:** Shipped · **Owner:** human · **Author:** agent · **Created:** 2026-09-24T21:45Z
**Constitution:** v1.0.0 · **Backlog row:** product.md §6 #006

## 1. Why
The challenge's Quality criterion asks whether the transcription "is accurate and
understandable, even with technical terms", and lists a glossary of technical terms and
proper names as an extra. Operators rarely have time to write one per talk. Diccionario
derives a first glossary from what every conference already has — the talk title and
abstract — and merges it with the manual list, so `custom_vocabulary` and the translation
prompt are primed before the first word is spoken. Moves **Quality** and **Innovation**.

## 2. User stories
- **US-1 (P0)** As an operator, I want the glossary to be filled automatically from the talk
  title and abstract, so that names and acronyms come out right without manual work.
- **US-2 (P1)** As an operator, I want my manual terms to always win and the total to stay
  within the model's sweet spot (≤ 100), so that automation never degrades a curated list.

## 3. Functional requirements
| ID | Requirement | Traces to |
|---|---|---|
| FR-006-01 | When `AUTO_GLOSSARY=true` and a stage has `talk.title` or `talk.abstract`, the runner MUST ask the auto-glossary engine for up to `AUTO_GLOSSARY_MAX_TERMS` prioritized terms (proper names, products, acronyms, jargon) before opening the first session; failures or timeouts MUST be logged and ignored (the stage starts with the manual glossary). | US-1 |
| FR-006-02 | The Gemini engine MUST use structured JSON output (`response_mime_type: application/json` + `response_json_schema` with a `terms: string[]` property) with the talk metadata delimited as data; the fake engine MUST use a deterministic heuristic (capitalized names, acronyms, mixed-case identifiers) so the dry run and tests need no network. | Art. IV, Art. VIII.4, Art. XII.2 |
| FR-006-03 | `merge_glossary(manual, auto)` MUST keep manual terms first, drop case-insensitive duplicates and cap the result at 100; the merged list MUST feed both `custom_vocabulary` (STT) and the translation prompt. | US-2 |
| FR-006-04 | The stage snapshot MUST expose `glossary_terms` (effective count) and `auto_glossary_terms` (added by automation); docs updated (configuration, customization). | Art. XI.2, Art. XVII.D.6 |

## 4. Non-functional requirements
| ID | Requirement | Measure |
|---|---|---|
| NFR-006-01 | Startup delay added by the auto-glossary call | ≤ 10 s timeout; the stage starts anyway on timeout |
| NFR-006-02 | Quality evidence | `make smoke-stt` with and without the glossary on the EN sample, WER recorded in `docs/metrics.md` |

## 5. Acceptance criteria (executable)
- **AC-1** Given the abstract "Kernel-level tracing with eBPF, Cilium and CoreDNS on Kubernetes", when the heuristic runs, then it returns `eBPF`, `Cilium`, `CoreDNS`, `Kubernetes` and no stop-words — verified by `pytest tests/test_auto_glossary.py`
- **AC-2** Given manual `["eBPF", "Nerdearla"]` and auto `["ebpf", "Cilium", …120 terms]`, when merged, then the result starts with the manual terms, has no duplicate `eBPF` and 100 entries — verified by `pytest tests/test_auto_glossary.py`
- **AC-3** Given a fake Gemini client returning `{"terms": ["Cilium", "Pixie"]}`, when the engine runs, then the request carries the JSON schema and the delimited talk, and the result is the two terms — verified by `pytest tests/test_auto_glossary.py`
- **AC-4** Given a stage with an abstract and `ENGINE=fake`, when the runner starts, then the session is opened with the merged glossary and the snapshot reports `auto_glossary_terms > 0` — verified by `pytest tests/test_runner.py::test_runner_applies_auto_glossary`
- **AC-5** `make smoke-stt` with and without the glossary recorded in `docs/metrics.md` — verified by the human at H3

## 6. Out of scope
Editing the glossary from the UI (ladder cut); learning terms from the transcript itself.

## 7. Open questions
- [x] Q1 Default on? → yes (`AUTO_GLOSSARY=true`), harmless without talk metadata

## Changelog
- 2026-09-24T21:45Z created; Status Approved.
- 2026-09-24T22:02Z Shipped: AC-1..4 by tests, AC-5 measured (docs/metrics.md); the heuristic
  ignores sentence-initial capitalized words (title case is not a name), documented in D-006-1.
