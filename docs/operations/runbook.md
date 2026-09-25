# Operations runbook

For the production team of any conference. Everything here uses the Admin page
(`/admin`, needs `ADMIN_TOKEN`) or plain `curl`. Lenguaraz is stateless: restarting the
container is always safe; only in-memory transcripts not yet exported are lost.

## Event-day checklist

**T-24h**
- [ ] `stages.yaml` lists every stage with the real `source` (SRT/RTMP/HLS URL or device), a
      `source_lang` hint, `targets`, `talk.title`/`abstract` and a `glossary` (product names,
      speakers, acronyms) — see `docs/configuration.md`.
- [ ] `.env`: `ENGINE=gemini`, a key from a project with **billing linked**, a long random `ADMIN_TOKEN`.
- [ ] Billing: project tier and prepay balance verified with `make smoke-stt` → `RESULT: PASS`.
      A `402 … prepayment credits are depleted` means the billing account is on the prepay
      plan with USD 0: buy credits (minimum USD 5) at https://aistudio.google.com/billing
      before the event; Cloud credits are consumed first once a prepay balance exists.
- [ ] Quota: the project's concurrent Live session limit (AI Studio) ≥ number of stages + 1
      (a rotation briefly needs two sessions per stage).
- [ ] `docker compose up --build`, then `curl http://<host>:8000/healthz` → `"status":"ok"`.
- [ ] Open `/admin`, enter the token, confirm every stage reaches `LIVE` with a test feed;
      open `/live/<stage>` on a phone over the venue Wi-Fi.
- [ ] Share `/live/<stage>` links (or the home page) with the audience; give the video team the
      overlay URLs `/overlay/<stage>?lang=<code>&lines=2`.

**T-1h**
- [ ] Feeds are live: state `LIVE`, `captions_final` increasing, `detail` empty.
- [ ] Latency p50/p95 in the Admin page look like the rehearsal numbers (`docs/metrics.md`).
- [ ] Spend cap: Tier 1 allows USD 10 per rolling 10 minutes; 10 stages cost ≈ USD 0.10 per
      minute all together (`docs/cost.md`).

**During**
- Watch `state` and `detail` per stage; `ROTATING` for a moment every ~9 minutes is normal.
- `errors` and `duplicates_dropped` should stay flat; `chunks_dropped` should not grow.
- A stage that shows `DEGRADED` keeps retrying on its own; see the playbooks below.

**After each talk**
- Export the transcript for every language from the Admin page (SRT/VTT/TXT buttons) or:

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://<host>:8000/api/admin/stages/main/export?format=srt&lang=es" -o main-es.srt
```

- Timestamps are positions on the stage's audio timeline (`00:00:00` = when the stage started
  receiving audio). If the stage started before the talk, shift the file in your subtitle tool.
- Stop stages that are finished for the day (`Stop` in the Admin page) to stop spending.

## Incident playbooks

| Situation | What you see | What to do |
|---|---|---|
| Stage `DEGRADED` (transient) | `detail: connect failed … retry n/5` or `send failed …` | Nothing for 30 s; it reconnects with backoff. If it reaches `STOPPED`, fix the cause (network, key) and press `Start`. |
| 429 quota | `detail: quota exhausted (429 …)` on one or more stages, or `translation to es failed: quota` | Check AI Studio: free tier, concurrent sessions or the 10-minute spend cap. Enable billing (with a prepay balance, see the next row) / raise the tier; temporarily stop non-essential stages or languages (`targets`). Captions resume on their own. |
| 402 billing (everything down at once) | Every stage `DEGRADED`/`STOPPED` with `402 … prepayment credits are depleted`; translations show the original text; `make smoke-stt` fails the same way | The Cloud Billing account is on the prepay plan with USD 0. Buy prepay credits (minimum USD 5) at https://aistudio.google.com/billing → **Buy credits**; within a minute or two calls succeed, press `Start` on stopped stages. Cloud credits are consumed first once a prepay balance exists. Alternative: unlink the project → free tier with `examples/env/free-tier.env`. Playbook below. |
| Network loss to Google | All stages `DEGRADED` at once | Check the venue uplink; stages reconnect automatically when it returns; audio received meanwhile is dropped after a 5 s backlog (`chunks_dropped`). |
| Wrong language transcribed | Captions in the wrong language, or garbled | Set `source_lang` for that stage (e.g. `["es-419"]`) instead of auto-detect; `Stop` + edit `stages.yaml` + restart the container. |
| Bad glossary | A term is consistently wrong or the translation keeps a wrong spelling | Fix the term in `glossary` (max 100), restart the stage. Terms are data: they cannot break the prompt. |
| Feed died (`STOPPED`, `ffmpeg exited`) | Detail shows the ffmpeg error | Fix the stream URL/encoder, press `Start`. |
| Audience page empty for one language | Translated captions show the original with a "degraded" mark | That language's translations are failing (quota/outage); originals keep flowing; it retries with the next final. |

## Restart and upgrade

```bash
docker compose pull && docker compose up -d --build   # picks up new stages.yaml too
```

Export transcripts first; a restart clears in-memory transcripts.

## Stage shows `stalls` > 0

**Symptom:** the Admin stage table shows a non-zero `stalls` counter; the log has
`no transcription for 20s while speech is flowing (stall)` followed by `ROTATING` → `LIVE`.

**Meaning:** the transcription session stopped answering while audio kept flowing; the
watchdog replaced it. One or two per hour is server-side variance and needs no action. Many
per hour: check the audio level (`ffmpeg` volume, `VAD_THRESHOLD`), the Gemini status page
and your project's concurrent-session quota; consider lowering `SESSION_ROTATE_SECONDS`.

## Translations pause with `rate limited (429)`

**Symptom:** stage detail `rate limited (429): translation to es paused for 57s; captions show the original text`; the audience sees the original language with an `original` marker for about a minute.

**Cause:** the Gemini project is on the free tier for the text model (`generate_content_free_tier_requests`, 15 requests per minute). Two stages with progressive translation make 40–60 requests per minute.

**Fix:** link a Cloud Billing account to the AI Studio project (Tier 1) and make sure it has a prepay balance (next section) — do this before the event. Mitigations meanwhile are bundled in `examples/env/free-tier.env`: `PROGRESSIVE_TRANSLATION=false` (halves the calls), `ALWAYS_ON_LANGS` empty so only languages with listeners are translated, `AUTO_GLOSSARY=false`, and fewer target languages — watch one stage and one language at a time. Lenguaraz never retries a 429; it waits for the server's hint and resumes on its own.

## Everything is DEGRADED/STOPPED with 402

**Symptom:** all stages fail at the same moment with detail `402 RESOURCE_EXHAUSTED: Your prepayment credits are depleted. Please go to AI Studio at https://ai.studio/projects`; translated captions show the original text; `make smoke-stt` fails with the same message. The key is valid and the network is fine.

**Cause:** the project is Tier 1 on a Cloud Billing account with the **prepay** plan (the default for new accounts) and the prepay balance is USD 0. Every request, Live transcription and text alike, is refused until credits are bought; Google Cloud promotional credits on the account do not help on their own, because they are consumed only once an active prepay balance exists.

**Fix (minutes):** https://aistudio.google.com/billing → confirm the billing account → **Buy credits** → the minimum, USD 5. Calls resume within a minute or two: press `Start` on each stopped stage (or `docker compose restart`) and confirm with `make smoke-stt` → `RESULT: PASS`. With the prepay balance in place the Cloud credits are consumed first.

**Alternative (no card):** unlink the project from the billing account; it returns to the free tier (15 text requests per minute, a handful of concurrent Live sessions). Restart from `examples/env/free-tier.env` and keep one stage and one language open. Not for a real event: the free tier may use content to improve Google products (`docs/privacy.md`).

**Prevention:** the T-24h checklist item "billing verified with `make smoke-stt`".
