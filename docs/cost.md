# Cost

All numbers below are **measured** by Lenguaraz's own tooling (`make smoke-stt`,
`make smoke-translate`, `make simulate`) and priced with the Gemini API public prices read on
**2026-09-22** (`lenguaraz/pricing.py`). Check the current prices before budgeting an event.

## Formula

```
cost ≈ stages × hours × (STT per stage-hour + Σ languages × translation per stage-hour)
```

- **Transcription** (`gemini-3.5-transcribe-live`): audio in at 25 tokens/s
  (USD 3.50 per 1M) plus the transcript text out (USD 21 per 1M). One session per stage,
  regardless of how many languages are served.
- **Translation** (`gemini-3.5-flash-lite`, USD 0.30 in / 2.50 out per 1M tokens): one short
  request per final caption per *active* language (always-on languages plus languages someone
  is reading, see `ALWAYS_ON_LANGS`). Progressive translation adds at most one extra request
  every `PROGRESSIVE_DEBOUNCE_MS` per language while the speaker talks.

## Measured

| What | Measured | Source |
|---|---|---|
| Transcription, per stage-hour | **USD 0.495** (2 real stages × 60 s in the mixed simulation: USD 0.0165) | `docs/scale-report.md`, 2026-09-24 |
| Translation EN → ES, per segment | 1,752 in / 102 out tokens for 5 segments → ≈ USD 0.0008, i.e. ≈ USD 0.16 per stage-hour per language at ~1,000 sentences/hour | `docs/metrics.md`, smoke-translate |
| Test audio generation (TTS, one-off) | ≈ USD 0.02 for both samples | GT-6.5 |

The Live transcription session did not report `usage_metadata` in our runs, so the STT text-out
part is estimated from characters ÷ 4; audio-in is exact (bytes sent ÷ 32,000 s).

## Worked example: 3-track conference, 2 days, 8 h/day

- 3 stages × 16 h = **48 stage-hours**
- Transcription: 48 × 0.495 ≈ **USD 24**
- Translation to Spanish (always on) + English on demand: 48 × 2 × 0.16 ≈ **USD 15**
- Total ≈ **USD 40** for the whole event, before any free credits. Add Portuguese on demand and
  it grows by ≈ USD 8 only while someone is actually reading it.

Compare with the speech-to-speech live translate model (USD 2.21 per stage-hour **per
language**, GT-6.2): the captions-first design is roughly four times cheaper per language and
the difference grows with every extra language.

## Quotas that cap you before cost does

- Concurrent Live sessions per project (visible in Google AI Studio); plan **stages + 1** for
  make-before-break rotation.
- Spend cap per rolling 10 minutes: Tier 1 USD 10, Tier 2 USD 50, Tier 3 USD 200 (GT-7.2).
  Ten stages cost about USD 0.10 per minute all together, far below Tier 1.
- The free tier limits requests per day per model and may use content to improve Google
  products; use a paid-tier project for real events (`docs/privacy.md`).
