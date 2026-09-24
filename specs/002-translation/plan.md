# Plan 002 — translation

**Spec:** specs/002-translation/spec.md (Approved) · **Created:** 2026-09-24T17:32Z

## 1. Constitution check (gate — all must be ✅ before tasks)
| Article | Status | Note |
|---|---|---|
| I Compliance | ✅ | Closes MVP-4 (EN → ES live); `make mvp-check` flips MVP-4 from PENDING to PASS |
| II Google terms | ✅ | Text model called server-side only; no new browser-to-Google path |
| III SDD traceability | ✅ | Tasks reference FR-002-xx / AC-x; commits carry `[T-002-xx]` |
| IV Docs-verified | ✅ | Interactions API surfaces listed in §2 with MCP chunk ids; verified against the installed SDK (`client.aio.interactions.create(**body)`, `InteractionSSEEvent`) |
| V Performance budgets | ✅ | `make smoke-translate` measures time-to-first-token and total per segment; translated caption latency = STT final latency + translation, both measured |
| VI Resilience | ✅ | Retries with backoff per translation; a failing language never blocks STT captions or other languages; `degraded` captions carry the original |
| VII Scale & cost | ✅ | One STT per stage; translations only for active languages (D8); `usage` per (stage, lang) recorded from `interaction.completed` |
| VIII Security | ✅ | Glossary/talk/context inserted as delimited, length-capped data; the system instruction states that tagged content is never a command; output is the translation only |
| IX Privacy | ✅ | Prompts are not logged unless `LOG_TRANSCRIPTS=true`; nothing persisted |
| X Accessibility | ✅ | Fogón already renders translated captions and "show original" (T-001-09) |
| XI Operability | ✅ | New env vars documented; troubleshooting entries for wrong language / glossary / quota |
| XII Tests | ✅ | `FakeTranslator`, fake Interactions client with scripted events, no network in tests |
| XIII Simplicity | ✅ | Per-language sequential worker (ordering for free); demand computed lazily at each final; no scheduler |
| XVII Open source & deployability | ✅ | No new dependencies; SPDX on new files; docs updated in the same feature |

## 2. Verified references (Article IV)
| API surface used | Verified via | URL / MCP query | Ground-truth ref |
|---|---|---|---|
| Interactions API is the default interface since June 2026; `generateContent` is legacy for new projects | MCP `gemini_get_doc` | `gemini-api-guides/index.md#interactions-api` | GT-9.2 |
| `client.interactions.create(model=…, input=…, stream=True)` streaming; events `step.start` / `step.delta` (`delta.type == "text"`, `delta.text`) / `step.stop` / `interaction.completed` (`interaction.usage.total_tokens`) | MCP `gemini_get_doc` | `gemini-api-guides/interactions/quickstart.md#3-stream-the-response`; `gemini-api-guides/interactions-breaking-changes-may-2026.md#core-change-outputs-to-steps/python-8` | — |
| Request body: `model`, `input` (string), `system_instruction` (string), `stream`, `generation_config{max_output_tokens, thinking_level: minimal|low|medium|high, thinking_summaries, stop_sequences, seed}`, `safety_settings` | MCP `gemini_get_doc` | `gemini-api-reference/interactions-api-v1.md#creating-an-interaction/request-body` | — |
| Python SDK: `await client.aio.interactions.create(**body)` returns `AsyncStream[InteractionSSEEvent]` when `stream=True`; `event.event_type`, `event.delta.type/text` | Installed `google-genai` 2.25 source (`google.genai._gaos.google_genai`) | introspected 2026-09-24T17:30Z | — |
| `gemini-3.5-flash-lite`: thinking `minimal` supported and default; "optimized for high-volume agentic tasks, translation" | MCP `gemini_get_doc` | `gemini-api-guides/generate-content/thinking.md#controlling-thinking/thinking-levels-gemini-3`; `gemini-api-guides/models/gemini-3.5-flash-lite.md` | GT-6.3, GT-13 |
| Pricing flash-lite $0.30 / $2.50 per 1M tokens | GT re-verified at T-000 | `ai.google.dev/gemini-api/docs/pricing` | GT-6.3 |
| Errors: `google.genai.errors.APIError` (`.code`, `.message`) | MCP `gemini_search_docs` | `python-sdk/README.md#google-gen-ai-sdk/error-handling` | GT-7.2 |

## 2b. Prior art applied
| Lesson / pattern (prior-art.md) | How this feature applies or improves it |
|---|---|
| PA-1 L1 — one shared model session per language, created on demand, torn down when idle | Text fan-out: one translation worker per (stage, language), created when the language becomes active, cancelled after the grace period (D8) |
| PA-2 — demand-set reconciliation with debounce and grace, unit-tested router | `translate/demand.py` computes `always_on ∪ listeners(grace)` as a pure function with unit tests (AC-2) |
| PA-2/PA-3 — captions tagged with target language, parallel to the original | `caption.lang` + `original` on every translated event; the client filters by `?lang=` |
| PA-1 gap — speech-to-speech model accepts no instructions ⇒ no glossary | Text translation with a delimited glossary and talk context; adherence measured by `make smoke-translate` |

## 3. Design

```
StageRunner._emit(original caption) ──▶ bus (lang = source)
                    │
                    └─▶ TranslationFanout.on_caption(event)
                            │  final: for lang in demand.active(stage) − {source}: queue[lang].put(event)
                            │  interim (PROGRESSIVE_TRANSLATION): debounced stable-prefix translation
                            │  pass-through: lang == source primary → publish at once
                            ▼
                    per-language worker (sequential, ordered by seq)
                            │  TranslationEngine.translate(request) → streamed text
                            │  retries 0.5/1/2 s on 429/5xx; on failure → caption(text="", degraded=True)
                            ▼
                    bus.publish(caption lang=es, original=…, same seq) → WS listeners on ?lang=es
```

- `translate/base.py` — `TranslationRequest(text, source_lang, target_lang, glossary, context, talk_title, talk_abstract)`, `TranslationResult`/usage, `TranslationEngine` protocol (`translate(request) -> AsyncIterator[str]`, `usage() -> TranslationUsage`).
- `translate/prompt.py` — `build_prompt(request) -> (system_instruction, input)`: system instruction fixes the task (professional conference interpreter, keep glossary terms verbatim, keep numbers/units, no preamble, translation only, tagged content is data); input carries `<glossary>`, `<talk>`, `<context>` (≤ 3 previous source/translation pairs) and `<text>`; caps enforced (glossary ≤ 100 terms / 2,000 chars, context ≤ 300 chars per segment, text ≤ 2,000 chars).
- `translate/gemini.py` — `GeminiTranslationEngine`: `client.aio.interactions.create(model=GEMINI_TRANSLATE_MODEL, input=…, system_instruction=…, generation_config={"thinking_level": GEMINI_TRANSLATE_THINKING, "max_output_tokens": TRANSLATE_MAX_OUTPUT_TOKENS}, stream=True)`; yields `delta.text` for `step.delta` events of type `text`; records usage from `interaction.completed`.
- `translate/fake.py` — `FakeTranslator`: deterministic `"[{target}] {text}"` (dry run shows the pipeline honestly), optional scripted failures and delays for tests.
- `translate/demand.py` — Baqueano: `LanguageDemand(always_on, grace_seconds)` with `observe(listeners, now)` and `active(now)`; pure and unit-tested.
- `translate/fanout.py` — Parla: `TranslationFanout(stage, engine, bus, settings, clock)`: `on_caption(event)`, per-language `asyncio.Queue` + worker task, context ring per language, retries, degraded captions, progressive translation state, `usage` per language, `active_languages()` for the snapshot.
- `runner.py` — creates the fanout when the stage has targets; `_emit` publishes the original then calls `fanout.on_caption`; `stop()` cancels workers; snapshot adds `active_languages` and `translation_tokens`.
- `tools/smoke_translate.py` — five EN segments from the sample script with the stage glossary → prints translations, time-to-first-token p50/p95, total p50/p95, tokens, glossary adherence; appends to `docs/metrics.md`.
- `tools/mvp_check.py` — unchanged; MVP-4 turns PASS when `es` captions with `original != text` arrive.

## 4. Contracts
- Caption events for translated languages: `{"type":"caption","lang":"es","source_lang":"en","seq":<same as source>,"is_final":…,"text":<translation>,"original":<source text>,"degraded":false}`; progressive interims use the same `seq` and `is_final:false`.
- Env: `ALWAYS_ON_LANGS` (comma-separated, default `es`), `LANG_GRACE_SECONDS` (10), `LANG_RECONCILE_DEBOUNCE_MS` (250, documented; the lazy reconcile evaluates at each final), `PROGRESSIVE_TRANSLATION` (true), `PROGRESSIVE_MIN_WORDS` (6), `PROGRESSIVE_DEBOUNCE_MS` (600), `TRANSLATE_MAX_OUTPUT_TOKENS` (512), `GEMINI_TRANSLATE_THINKING` (`minimal`), `TRANSLATE_CONTEXT_SEGMENTS` (3).
- `/api/stages` rows gain `active_languages: ["es"]` and `translation_tokens: {"es": {"input": n, "output": n}}`.

## 5. Dependencies added (justify each)
| Package | Version | License (SPDX) | Allowed per Art. XVII.B? | Why |
|---|---|---|---|---|
| — | — | — | — | No new dependencies; the Interactions API ships in `google-genai` |

## 6. Risks & mitigations
| Risk | Likelihood | Mitigation |
|---|---|---|
| Interactions API event shape differs from the docs in the installed SDK | Medium | Engine reads events defensively (`getattr`) and is unit-tested with scripted events; `make smoke-translate` validates the real shape before M2 |
| Model adds preambles or quotes | Medium | System instruction demands translation only; post-process strips surrounding quotes/labels; adherence measured |
| Translation latency stacks on STT final latency | Medium | `thinking_level: minimal`, streaming first token, per-language concurrency; progressive translation on partials |
| Sequential per-language worker falls behind on a 429 storm | Low | Retries capped (3), degraded captions published fast, queue bounded (drop oldest interim requests) |
| Prompt injection via glossary/talk metadata | Low | Delimited tags, caps, explicit "data, not instructions" rule; tests assert the delimiters |

## 7. Verification strategy
Unit tests with `FakeTranslator` and a fake Interactions client (prompt builder, demand, fan-out ordering, pass-through, retries/degraded, progressive rule); e2e fake test through the WebSocket (`?lang=es` receives translated captions); `make mvp-check` MVP-4 PASS in fake and real mode; `make smoke-translate` with the real model for latency/tokens/adherence; docs-check for the new keys.
