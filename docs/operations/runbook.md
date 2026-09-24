# Operations runbook

For the production team of any conference. Everything here uses the Mangrullo page
(`/mangrullo`, needs `ADMIN_TOKEN`) or plain `curl`. Lenguaraz is stateless: restarting the
container is always safe; only in-memory transcripts not yet exported are lost.

## Event-day checklist

**T-24h**
- [ ] `stages.yaml` lists every stage with the real `source` (SRT/RTMP/HLS URL or device), a
      `source_lang` hint, `targets`, `talk.title`/`abstract` and a `glossary` (product names,
      speakers, acronyms) — see `docs/configuration.md`.
- [ ] `.env`: `ENGINE=gemini`, a key from a **paid-tier** project, a long random `ADMIN_TOKEN`.
- [ ] Quota: the project's concurrent Live session limit (AI Studio) ≥ number of stages + 1
      (a rotation briefly needs two sessions per stage).
- [ ] `docker compose up --build`, then `curl http://<host>:8000/healthz` → `"status":"ok"`.
- [ ] Open `/mangrullo`, enter the token, confirm every stage reaches `LIVE` with a test feed;
      open `/fogon/<stage>` on a phone over the venue Wi-Fi.
- [ ] Share `/fogon/<stage>` links (or the home page) with the audience; give the video team the
      overlay URLs `/pizarron/<stage>?lang=<code>&lines=2`.

**T-1h**
- [ ] Feeds are live: state `LIVE`, `captions_final` increasing, `detail` empty.
- [ ] Latency p50/p95 in Mangrullo look like the rehearsal numbers (`docs/metrics.md`).
- [ ] Spend cap: Tier 1 allows USD 10 per rolling 10 minutes; 10 stages cost ≈ USD 0.10 per
      minute all together (`docs/cost.md`).

**During**
- Watch `state` and `detail` per stage; `ROTATING` for a moment every ~9 minutes is normal.
- `errors` and `duplicates_dropped` should stay flat; `chunks_dropped` should not grow.
- A stage that shows `DEGRADED` keeps retrying on its own; see the playbooks below.

**After each talk**
- Export the transcript for every language from Mangrullo (SRT/VTT/TXT buttons) or:

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://<host>:8000/api/admin/stages/main/export?format=srt&lang=es" -o main-es.srt
```

- Timestamps are positions on the stage's audio timeline (`00:00:00` = when the stage started
  receiving audio). If the stage started before the talk, shift the file in your subtitle tool.
- Stop stages that are finished for the day (`Stop` in Mangrullo) to stop spending.

## Incident playbooks

| Situation | What you see | What to do |
|---|---|---|
| Stage `DEGRADED` (transient) | `detail: connect failed … retry n/5` or `send failed …` | Nothing for 30 s; it reconnects with backoff. If it reaches `STOPPED`, fix the cause (network, key) and press `Start`. |
| 429 quota | `detail: quota exhausted (429 …)` on one or more stages, or `translation to es failed: quota` | Check AI Studio: free tier, concurrent sessions or the 10-minute spend cap. Enable billing / raise the tier; temporarily stop non-essential stages or languages (`targets`). Captions resume on their own. |
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
