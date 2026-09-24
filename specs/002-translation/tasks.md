# Tasks 002 — translation

**Plan:** specs/002-translation/plan.md · Legend: `[P]` parallelizable · `[H]` needs human · each task ≤ 45 min.

| ID | Task | Refs | Verify | Status |
|---|---|---|---|---|
| T-002-01 | Settings (`ALWAYS_ON_LANGS`, `LANG_GRACE_SECONDS`, `LANG_RECONCILE_DEBOUNCE_MS`, `PROGRESSIVE_MIN_WORDS`, `PROGRESSIVE_DEBOUNCE_MS`, `TRANSLATE_MAX_OUTPUT_TOKENS`, `GEMINI_TRANSLATE_THINKING`, `TRANSLATE_CONTEXT_SEGMENTS`) and `translate/prompt.py` with delimiters and caps; failing tests first | FR-002-02, AC-1 | `uv run pytest tests/test_translate_prompt.py` | ☑ |
| T-002-02 | `translate/base.py` (request/usage/engine protocol), `translate/fake.py` (`FakeTranslator`), `translate/gemini.py` (Interactions streaming, usage, error classification); unit test with a scripted Interactions client | FR-002-01, FR-002-09 | `uv run pytest tests/test_translate_gemini.py` | ☑ |
| T-002-03 | Baqueano `translate/demand.py`: `always_on ∪ listeners` with grace; pure function + tests | FR-002-04, AC-2, NFR-002-05 | `uv run pytest tests/test_demand.py` | ☑ |
| T-002-04 | Parla `translate/fanout.py`: per-language ordered workers, pass-through, context ring, retries + degraded captions + status detail, usage per language; tests | FR-002-03, FR-002-05, FR-002-07, AC-3, AC-4, AC-6 | `uv run pytest tests/test_fanout.py` | ☑ |
| T-002-05 | Progressive translation of the stable prefix (debounce, min words, replaced by the final) behind `PROGRESSIVE_TRANSLATION`; tests | FR-002-06, AC-5 | `uv run pytest tests/test_progressive.py` | ☑ |
| T-002-06 | Runner + API integration: fan-out per stage, snapshot fields (`active_languages`, `translation_tokens`), e2e fake test over `/ws/main?lang=es`; `make mvp-check` MVP-4 PASS in fake mode | FR-002-08, AC-8, AC-9 | `uv run pytest tests/test_e2e_fake.py && make mvp-check` | ☑ |
| T-002-07 [H quota] | `tools/smoke_translate.py` + `make smoke-translate`: five EN segments, glossary adherence ≥ 95 %, TTFT and total p50/p95, tokens → `docs/metrics.md`; then `MVP_ARGS="--engine gemini" make mvp-check` | FR-002-11, AC-7, NFR-002-02/04 | `make smoke-translate` | ☑ |
| T-002-08 | Docs-as-you-go: `docs/configuration.md` (new keys), `docs/architecture.md` (fan-out + demand), `docs/customization.md` (languages, glossary), `docs/troubleshooting.md` (wrong language, glossary term mistranslated, translation quota); `make docs-check` | FR-002-10, AC-10 | `make docs-check` | ☑ |
| T-002-09 [H] | **H2** — live MVP demo in the owner's browser: two stages, EN → ES live, language switch; approve tag `v0.1.0`. **= M2 exit** | Art. I.5, H2 | human verdict + `git tag v0.1.0` | ☐ |
| T-002-10 | Converge: spec vs code, mark spec 002 Shipped, README "What it does today" + STATE.md | Art. III.3 | `make verify && make mvp-check` | ☐ |

## Estimate vs clock
Started 17:33Z; M2 deadline 21:00Z (3h27m). Order is strict T-01 → T-06 (≈ 2 h), then T-07/T-08 in parallel (≈ 30 min), H2 at ≈ 20:15Z. If T-06 is not green by **19:45Z**, cut T-05 (progressive translation, ladder item 5) and ship final-only translation.

## Definition of Done (feature)
- [ ] All tasks ☑ and all ACs pass
- [ ] `make verify` green
- [ ] Docs updated per Art. XVII.D.6 (configuration / architecture / customization / troubleshooting)
- [ ] New files carry SPDX headers; `make license-check` green (007) — `make spdx-check` green now
- [ ] STATE.md updated, `v0.1.0` tagged after H2
