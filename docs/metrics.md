# Metrics

Measured by the project's own tooling (Constitution Art. V.2); definitions below.

## Definitions

- **Per caption `latency_ms`** (live, every event): interim = milliseconds since the previous
  partial update of the same utterance (0 for the first); final = commit delay between the
  last partial update and the committed line. The `metrics` event and `/api/stages` report
  p50/p95 of the final commit delay over the last 200 captions.
- **Speech-to-caption latency** (measured offline with known sentence boundaries by
  `make smoke-stt` on the bundled samples, whose `.json` files carry the exact start and
  end of every sentence): *utterance-to-final* = wall time of the final caption minus the
  wall time at which the sentence ended in the audio; *first partial* = wall time of the
  first partial caption of a sentence minus the wall time at which the sentence started.
- **Word error rate** = `jiwer` WER between the reference transcript and the concatenated
  finals, after lower-casing and stripping punctuation (SMART mode formats numbers, which
  counts as errors against a spelled-out reference).
- **Cost** = audio seconds × 25 tokens/s × input price + response tokens × output price
  (pricing from ground truth GT-6, 2026-09-22). When the Live API sends no `usage_metadata`
  for a transcription session, output tokens are estimated as characters ÷ 4.

## smoke-stt runs

| Date (UTC) | Sample | Mode | Finals | WER | First partial p50/p95 ms | Utterance-to-final p50/p95 ms | Commit delay p50/p95 ms | Tokens (in/out) | Est. cost USD |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-24 17:09 | es_asyncio.wav | SMART | 7 | 4.3% | 2809/14823 | 3981/15932 | 156/391 | 0/0 | 0.0072 |

### Notes

- **Method for the smoke rows:** the sample is replayed in real time through the same
  ingest → `ManagedSttSession` → Gemini Live path the service uses; the wall clock is
  anchored to the first chunk read from the source, and the sample's `.json` sentence
  boundaries give the true start/end of every sentence.
- **2026-09-24 17:23–17:25Z (paid tier, `VAD_MODE=hybrid`, default):** 7/7 sentences
  finalized on every run, WER 3.2 % (EN) with the SMART formatting differences
  ("300", "2 million") counted as errors. Hybrid VAD (client-side silence → `audio_stream_end`)
  yields more partial updates (37–48 per 33 s) and a shorter sentence-end → final time than
  the server VAD alone (5 partials, p50 1.19 s).
- **Earlier rows (17:09, free tier, server VAD):** the server sometimes finalized only at
  stream end, which produced utterance-to-final p95 of 15 s. Rows from broken sample audio
  (a half-speed clip caused by assuming 24 kHz for a 48 kHz TTS answer) were removed; see
  `docs/decisions.md` D-001-3/D-001-4.
- The Live transcription session sent no `usage_metadata`; cost is estimated from audio
  seconds (25 tokens/s) plus response characters ÷ 4.
| 2026-09-24 17:27 | es_asyncio.wav | SMART | 7 | 4.3% | 2359/5044 | 777/981 | 469/1234 | 0/0 | 0.0072 |

## smoke-translate runs

| Date (UTC) | Direction | Segments | TTFT p50/p95 ms | Total p50/p95 ms | Glossary adherence | Tokens (in/out) | Est. cost USD |
|---|---|---|---|---|---|---|---|
| 2026-09-24 21:01 | en-US→es | 5 | 687/2594 | 750/2954 | 8/8 (100%) | 1752/102 | 0.0008 |
| 2026-09-24 21:01 | es-419→en | 3 | 844/7343 | 891/7468 | 3/3 (100%) | 919/45 | 0.0004 |
