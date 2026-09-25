# Spec 002 — translation

**Status:** Shipped (H2 OK 2026-09-24T22:40Z) · **Owner:** human · **Author:** agent · **Created:** 2026-09-24T16:02Z
**Constitution:** v1.0.0 · **Backlog row:** product.md §6 #002

## 1. Why
The lenguaraz's job is that everyone understands in their own language. This feature turns the single transcription stream of each stage into captions in every requested language: English → Spanish live (MVP-4), plus English and Portuguese where wanted. It is text fan-out from one STT stream (cost grows with stages, not stages × languages), glossary-aware so technical terms and proper names survive translation (**Quality**), demand-driven so a language costs nothing until someone reads it (**Scalability**, prior-art D8), and optionally progressive so translated captions appear while the speaker is still talking (**Latency**, **Innovation**).

## 2. User stories
- **US-1 (P0)** As an audience member at an English talk, I want to choose Spanish and read translated captions within a few seconds of each sentence, so that I can follow without knowing English.
- **US-2 (P0)** As a production operator, I want to give each stage a glossary (product names, speakers, event names) that the translation must keep verbatim, so that captions do not mangle the terms the talk is about.
- **US-3 (P1)** As an organizer, I want a language to cost money only while someone is reading it, except the languages I mark always-on, so that offering ten languages does not multiply the bill.
- **US-4 (P1)** As an audience member reading the same language the speaker uses (or a speaker who switches languages), I want the original text passed through instead of a round trip through the model, so that captions stay instant and exact.
- **US-5 (P2)** As an audience member, I want to see a provisional translation while the speaker is mid-sentence, so that the translated line lags the speech as little as possible.

## 3. Functional requirements
| ID | Requirement | Traces to |
|---|---|---|
| FR-002-01 | **Engine interface:** a `TranslationEngine` with `translate(text, source_lang, target_lang, glossary, context) -> AsyncIterator[str]` (streamed text), a Gemini implementation using the official SDK with the text model from `GEMINI_TRANSLATE_MODEL` (streaming, minimal thinking budget, temperature low), and a `FakeTranslator` that returns a deterministic marked translation for tests and dry run. | US-5 (contributor) · Art. IV · Art. XII.2 |
| FR-002-02 | **Prompt safety:** glossary terms, talk title/abstract and previous segments MUST be inserted as clearly delimited data, length-capped (glossary ≤ 100 terms / 2,000 chars, context ≤ 3 previous final segments), and the instruction MUST state that delimited content is never a command; the model output MUST be the translation only (no preamble). | Art. VIII.4 · CLAUDE.md §7 |
| FR-002-03 | **Parla (fan-out):** for every final caption of a stage, the system MUST translate to each *active* target language concurrently and publish a `caption` event per language with `lang`, `source_lang`, `text` (translation), `original` (source text) and the same `seq` as the source caption; ordering per language MUST be preserved by `seq`. | MVP-4 · D3 · Art. VII.1 |
| FR-002-04 | **Baqueano (demand):** the active language set per stage MUST equal `always_on` ∪ {languages with ≥ 1 connected listener}, where `always_on` = `ALWAYS_ON_LANGS` (env, default `es`) ∩ stage `targets`; reconciliation MUST be debounced by `LANG_RECONCILE_DEBOUNCE_MS` (default 250) and a language MUST stay active for `LANG_GRACE_SECONDS` (default 10) after its last listener leaves; the metric `lenguaraz_active_languages{stage}` MUST reflect it. | US-3 · D8 · PA-1 L1 · PA-2 |
| FR-002-05 | **Pass-through:** when the segment's source language equals the target (by primary subtag, e.g. `en-US` → `en`), the caption MUST be published immediately with `text == original` and no engine call. | US-4 · D3 |
| FR-002-06 | **Progressive translation** (`PROGRESSIVE_TRANSLATION`, default `true`): the system MUST translate the stable prefix of the interim hypothesis (unchanged for ≥ 600 ms and ≥ 6 words) and publish it as an interim caption for each active target; the final translation MUST replace it under the same `seq`; the feature MUST be measurable (extra calls, tokens and latency gain recorded in `docs/metrics.md`) and removable by flag (scope-cut ladder #5). | US-5 · D4 · Art. V |
| FR-002-07 | **Resilience:** transient engine errors MUST retry with exponential backoff + jitter (max 3); on persistent failure or `429` the stage MUST publish `status` with `detail` naming translation and the language while STT captions keep flowing; a failed translation MUST publish the caption with `original` and `text=""` plus `degraded=true` so the client can show the original instead of nothing. | Art. VI.2–3 |
| FR-002-08 | **Fogón:** the language picker MUST list `source_lang` and `targets`; selecting a language MUST resubscribe the WebSocket with `?lang=`; the UI MUST show the original beneath the translation when the user enables "show original". | MVP-7 · US-1 |
| FR-002-09 | **Usage accounting:** every engine call MUST record `usage_metadata` tokens (input, output, thinking) per stage and language; totals MUST be exposed in the `metrics` event and logged, as the source for `docs/cost.md`. | Art. VII.3 |
| FR-002-10 | **Docs-as-you-go:** `docs/configuration.md` (new env vars), `docs/architecture.md` (fan-out and demand loop), `docs/customization.md` (languages, glossary), `docs/troubleshooting.md` (wrong language detected, glossary term still mistranslated, translation quota) MUST be updated in this feature. | Art. XVII.D.6 |
| FR-002-11 | `make smoke-translate` MUST translate five sample segments with a glossary through the real API and print translations, p50/p95 latency and token counts; `make mvp-check` MUST verify MVP-1..7 end to end in fake mode and, when a key is present, in real mode. | Art. I.5 · Art. XII |
| FR-002-14 | On HTTP 429 the fan-out MUST NOT retry: it pauses that language for the server's retry hint (5–120 s, default 30 s), publishes the caption with the **original text** and `degraded=true`, skips progressive partials while paused, reports the pause in the stage detail and counts it (`translation_rate_limited`). Degraded captions always carry the original text, never an empty line. | Free tier: 15 requests/min (measured 2026-09-24) |

## 4. Non-functional requirements
| ID | Requirement | Measure |
|---|---|---|
| NFR-002-01 | Translated caption visible after end of utterance | p95 ≤ 3.0 s (final STT latency + translation), measured by `make smoke-stt` + `make smoke-translate` on the EN sample; recorded in `docs/metrics.md` |
| NFR-002-02 | Translation call latency for segments ≤ 40 words | p95 ≤ 1.2 s to first token, measured by `make smoke-translate` |
| NFR-002-03 | Cost per stage-hour per language for text translation | < 10 % of the STT cost, computed from recorded `usage_metadata` and the pricing in GT-6 |
| NFR-002-04 | Glossary adherence | ≥ 95 % of glossary terms present in the source appear verbatim in the translation over the 5-segment smoke set (checked by the smoke script) |
| NFR-002-05 | Demand reconciliation | A new language becomes active ≤ 500 ms after its first listener connects (debounce + first call), verified with fakes |

## 5. Acceptance criteria (executable)
- **AC-1** Given glossary `["Kubernetes", "Nerdearla"]`, a title and two previous segments, when the prompt is built, then the glossary and context appear inside delimiters, the total stays within caps and the instruction forbids treating them as commands — verified by `pytest tests/test_translate_prompt.py`
- **AC-2** Given a stage with targets `[es, pt]` and `ALWAYS_ON_LANGS=es`, when no listener is connected, then active = `{es}`; when a `pt` listener connects, `pt` becomes active within 500 ms; when it disconnects, `pt` stays active 10 s and is then removed — verified by `pytest tests/test_demand.py`
- **AC-3** Given a final EN caption and active languages `{es, pt}` with the fake engine, when fan-out runs, then one caption per language is published with the source `seq`, `lang`, `original` and translated `text` — verified by `pytest tests/test_fanout.py`
- **AC-4** Given a stage whose source language is `en-US` and a listener on `en`, when a final arrives, then the caption is published at once with `text == original` and the engine is never called — verified by `pytest tests/test_fanout.py::test_passthrough`
- **AC-5** Given `PROGRESSIVE_TRANSLATION=true` and interims "we are going", "we are going to talk about eBPF today, and", when the stable prefix rule triggers, then an interim translated caption is published and later replaced by the final translation under the same `seq` — verified by `pytest tests/test_progressive.py`
- **AC-6** Given an engine that fails twice then succeeds, when translating, then the caption is published and two retries are logged; given an engine that always returns 429, then a `status` event names the translation quota problem, the caption is published with `degraded=true` and STT captions keep arriving — verified by `pytest tests/test_fanout.py::test_errors`
- **AC-7** Given `GEMINI_API_KEY`, when `make smoke-translate` runs, then five EN→ES translations print with p50/p95 latency and tokens, and glossary adherence ≥ 95 % — verified by `make smoke-translate` (human confirms quota)
- **AC-8** Given the two sample stages in fake mode, when `make mvp-check` runs, then MVP-1..7 are each reported PASS; given a key, `ENGINE=gemini make mvp-check` also passes — verified by `make mvp-check` and by the human at H2
- **AC-9** Given the Fogón page for a stage with targets, when the user selects Spanish, then the WebSocket reconnects with `?lang=es` and Spanish captions replace the English ones — verified by `cd web && npm test`
- **AC-10** Given the docs, when `make docs-check` runs, then `ALWAYS_ON_LANGS`, `LANG_GRACE_SECONDS`, `LANG_RECONCILE_DEBOUNCE_MS`, `PROGRESSIVE_TRANSLATION` and `GEMINI_TRANSLATE_MODEL` are documented — verified by `make docs-check`

## 6. Out of scope
- Spoken interpretation (live translate model, feature 010); Gemma engine (011).
- Auto-glossary from title/abstract (006): this feature only consumes a glossary.
- Glossary editing UI (004); this feature reads `stages.yaml`.
- Translation of interim text beyond the stable-prefix rule (full speculative translation is not attempted).

## 7. Open questions
- [x] Q1 Target languages per stage (`targets`) plus a global `ALWAYS_ON_LANGS` (default `es`)? (blocking? no · default: yes) → default applied
- [x] Q2 Progressive translation on by default? (blocking? no · default: on, flag documented, first candidate to cut if behind schedule) → default applied
- [x] Q3 Target codes: short codes (`es`, `en`, `pt`) in UI and `targets`; STT keeps BCP-47 (`en-US`); matching by primary subtag. Portuguese target rendered as Brazilian Portuguese in the prompt. (blocking? no · default: yes) → default applied
- [x] Q4 Which text model? (resolved: `gemini-3.5-flash-lite`, GT-6.3 / GT-13; configurable)

## Changelog
- 2026-09-24T16:02Z created; Q1–Q4 resolved with defaults per CLAUDE.md §5 (logged in HUMAN_INBOX.md); Status Approved.
- 2026-09-24T23:05Z FR-002-14 added: rate-limit cooldown and original text in degraded captions (the live demo on a free-tier project degraded ~30 % of translations to empty lines).
- 2026-09-25T14:05Z Owner decision during the demo: each language view shows only its own language. FR-002-14 amended: a failed, timed-out or rate-limited translation is skipped in that language (counted as `translation_untranslated`), never shown as source text.
