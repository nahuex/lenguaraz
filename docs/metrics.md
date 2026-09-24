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
| 2026-09-24 17:13 | en_kubernetes.wav | SMART | 6 | 17.9% | 782/14295 | 781/15138 | 125/454 | 0/0 | 0.0055 |

### Notes

- 2026-09-24 17:12Z EN run: 6 of 7 sentences finalized; the 7th final arrived only after `audio_stream_end` and fell outside the 3 s drain window. Finals 4–6 were emitted together at the end of the stream (server VAD did not finalize on the 1.5 s gaps), which is why the utterance-to-final p95 is 15 s while p50 is 0.8 s. Hybrid VAD (client-side silence → `audio_stream_end`) is the planned fix.
- WER against a spelled-out reference includes SMART-mode number formatting ("300", "2 million").
- The Live transcription session sent no `usage_metadata`; cost is estimated from audio seconds.
