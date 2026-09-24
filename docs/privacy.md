# Privacy

What Lenguaraz does with speech, text and visitor data, what it keeps and for how long, and
the notices a conference should give. Written for the organizer who has to answer a speaker,
an attendee or a data-protection officer. Security controls are in [`security.md`](security.md).

## Roles

The conference that runs Lenguaraz decides what is captured and where it goes; Lenguaraz is
software you host, not a service. Google's Gemini API processes the audio and text you send
it under Google's terms. In GDPR language the organizer is typically the controller and Google
a processor or sub-processor; confirm that reading with your own counsel.

## What flows where

| Data | From → to | Transport | Purpose |
|---|---|---|---|
| Stage audio | Your source (file, HLS, RTMP, SRT, device) → ffmpeg on your server → 16 kHz PCM chunks → **Gemini Live API** (`GEMINI_STT_MODEL`) | Server to Google, TLS, official SDK | Live transcription |
| Final captions + glossary + talk title/abstract + the previous `TRANSLATE_CONTEXT_SEGMENTS` (default 3) sentence pairs | Server → **Gemini text model** (`GEMINI_TRANSLATE_MODEL`) | Server to Google, TLS; the Interactions transport is called with `store=False` | Translation, one request per final caption per active language |
| Talk title and abstract | Server → Gemini text model, once per stage start | Server to Google, TLS | Auto-glossary (`AUTO_GLOSSARY`) |
| Captions (original and translated), stage state, metrics | Server → every browser on `/ws/{stage}` | WebSocket (TLS through your proxy) | Audience view, overlay |
| Transcripts | Server memory → a file the operator downloads from `/api/admin/stages/{id}/export` | Bearer-authenticated HTTP | SRT/VTT/TXT after a talk |

The audience never sends audio or text: the caption socket accepts only `ping`. Nothing about
a viewer is sent to Google.

## Retention

| Data | Where | How long |
|---|---|---|
| Audio | Bounded in-memory queues between ffmpeg and the Live session | Seconds. Never written to disk, never kept after transcription |
| Interim captions | Bus queues, browser memory | Until replaced by the final caption |
| Final captions | `TranscriptStore` in memory, per stage and language, at most 5,000 entries each | Until the process stops (a restart clears them) or the deque overflows |
| Exports | Files the operator downloads (`exports/` is git-ignored if you save them in the repo folder) | Yours to keep or delete |
| Token counts, latency, cost estimate | In memory, aggregated numbers only | Until the process stops |
| Google-side retention of prompts and audio | Google's systems | Per Google's terms and your project tier; see below |

## What is logged

Logs are JSON lines on stderr with `stage_id`, `session_id`, `seq`, `component` and `lang`.
By default they hold stage state changes, session ids, error messages and one line per
audience connection with the client IP (`listener connected from <ip>`). Caption text is
logged only when `LOG_TRANSCRIPTS=true`; keep it `false` at real events. Audio and the API key
are never logged. Log retention is whatever your container runtime or log shipper does with
stderr (`docker compose logs`), so set a rotation policy there.

## Paid tier versus free tier

Per Google's terms at the time of writing (September 2026), content sent through an
**unpaid** (free-tier) Gemini API project may be used to improve Google's products and may be
reviewed by humans; content sent through a **paid-tier** project is not used that way. Speaker
audio is third-party content you are responsible for, so use a project with billing enabled
for any real event and read the current text before you commit to a privacy statement:
https://ai.google.dev/gemini-api/terms. The free tier also limits concurrent Live sessions,
which matters for multi-stage events (see [`deploy/scaling.md`](deploy/scaling.md)).

## 18+ operator notice

The Gemini API requires its users to be 18 or older, and API clients must not be directed
at, or likely to be accessed by, people under 18. The person operating Lenguaraz must be an
adult, and the captions service must not be marketed to minors. Under-18 attendees reading
captions at a general-audience conference are not the target of the service; if your event
is for minors, do not deploy Lenguaraz with the Gemini engine.

## Tell speakers and the audience

Captions are machine-generated and speech leaves your venue to be transcribed. A short
notice in the speaker briefing and on the captions page covers both. Suggested text:

> Live captions and translations on this stage are generated automatically by an AI service
> (Google Gemini) from the stage audio. Audio is processed in real time and not stored by the
> conference; captions may be exported as a transcript. Captions can contain errors.

Speakers who do not want their talk transcribed can be left out: remove the stage from
`stages.yaml` or press **Stop** in the Admin page for that slot.

## GDPR-style notes

- **No accounts, no tracking.** The audience page has no login, no analytics and no cookies.
- **Browser storage.** Viewer preferences live in `localStorage` under `lenguaraz.fontSize`,
  `lenguaraz.highContrast`, `lenguaraz.theme` and `lenguaraz.showOriginal`; the operator page
  keeps the admin token in `sessionStorage` (`lenguaraz.adminToken`) until the tab closes.
  Nothing in browser storage identifies a person or is read back by the server.
- **IP addresses** are counted in memory while a socket is open (`WS_MAX_CONN_PER_IP`) and
  appear in the connection log line; Lenguaraz keeps no database of them. Behind a proxy the
  server sees the proxy's address unless you forward client IPs (see `security.md`).
- **Transcripts are personal data** when a speaker is identifiable. Export them only when
  you need them, store them where your other event records live, and delete them per policy.
- **Data location.** Requests go to the Gemini API endpoint used by the official SDK; the
  processing region is Google's. Do not promise a region unless Google's terms let you.
- **Access requests.** Nothing is retrievable per person: there are no viewer records, and
  speaker text exists only in exports you control.

## Questions to settle before the event

1. Which project tier holds the API key, and who verified the terms that apply to it?
2. Which stages are transcribed, and were the speakers told?
3. Who receives the exports, where are they stored, and when are they deleted?
4. Is `LOG_TRANSCRIPTS` off and is log rotation configured?
5. Does the captions page or the program carry the AI-captions notice?
