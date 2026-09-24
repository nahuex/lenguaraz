# Audio sources — feeding a stage

Every stage has one `source` in `stages.yaml`. Lenguaraz opens it with **ffmpeg** and turns it
into 16 kHz mono PCM for the transcription session (one ffmpeg process per stage, killed when
the stage stops). Anything ffmpeg can read works: a file, an HLS or RTMP or SRT URL, an RTSP
camera, an HTTP audio stream. The only exception is a local **16 kHz mono WAV**, which is read
with the standard library and needs no ffmpeg at all (that is what the dry run and the
bundled samples use).

```yaml
stages:
  - id: main
    name: "Main Stage"
    source: "srt://0.0.0.0:9000?mode=listener"   # ← this line
    source_lang: ["en-US"]
    targets: ["es"]
```

How the source is handled:

| `source` looks like | What happens |
|---|---|
| `something.wav` (16 kHz, mono, PCM) | Read directly, paced at real time; `loop: true` replays it forever (demo stages). |
| any other local file with an extension (`talk.mp3`, `talk.mp4`, `talk.m4a`) | `ffmpeg -re -i file …` (real-time pacing, `loop: true` supported). |
| anything with `://` | `ffmpeg -i URL …` as fast as the stream delivers (live pacing comes from the stream). |

ffmpeg must be on the `PATH` or pointed to with `FFMPEG_BIN=/path/to/ffmpeg`. The Docker image
ships it. Only audio is used (`-vn`); video streams are fine as input.

## Recipes

### A file (rehearsals, post-event captions)

```yaml
source: "recordings/keynote.mp4"
```

Any container or codec. For a quick test of your own audio, convert it once to the fast path:

```bash
ffmpeg -i talk.mp3 -ac 1 -ar 16000 -acodec pcm_s16le talk.wav
```

### SRT (recommended for venues)

SRT is what most encoders (OBS, vMix, Blackmagic Web Presenter, Haivision) speak, it crosses
NATs and recovers from packet loss. Let Lenguaraz **listen** and point the encoder at it:

```yaml
source: "srt://0.0.0.0:9000?mode=listener&latency=200000"
```

Encoder side (OBS: Settings → Stream → Service *Custom*, Server `srt://<lenguaraz-host>:9000?mode=caller`,
any audio-capable output; or from the command line):

```bash
ffmpeg -re -i input.mp4 -c:a aac -b:a 96k -f mpegts "srt://LENGUARAZ_HOST:9000?mode=caller"
```

Open UDP port 9000 on the host / security group. One port per stage (`9001`, `9002`, …).
`latency` is in microseconds; 200 ms is a good LAN/venue default, 500 ms over the internet.

### RTMP (from OBS / vMix / a streaming encoder)

Lenguaraz does not run an RTMP server. Point the encoder at your existing media server
(nginx-rtmp, MediaMTX, Wowza, a cloud ingest) and give Lenguaraz the **pull** URL:

```yaml
source: "rtmp://media.example.org/live/main"
```

With [MediaMTX](https://github.com/bluenviron/mediamtx) on the same host, publishing to
`rtmp://host/main` makes `rtmp://127.0.0.1/main` and `rtsp://127.0.0.1:8554/main` available.

### HLS (an already-published stream)

```yaml
source: "https://cdn.example.org/live/main/index.m3u8"
```

Expect HLS to add its segment length (typically 2–6 s) to the caption latency; use SRT or
RTMP when you control the encoder.

### OBS or vMix on the same machine (no streaming service)

Use the encoder's **recording/stream to SRT** feature with the SRT listener recipe above, or
send the program audio to a local loopback and capture it with ffmpeg on the capture machine:

```bash
# Windows (dshow): list devices with  ffmpeg -list_devices true -f dshow -i dummy
ffmpeg -f dshow -i audio="CABLE Output (VB-Audio Virtual Cable)" -c:a aac -f mpegts "srt://LENGUARAZ_HOST:9000?mode=caller"

# macOS (avfoundation): list with  ffmpeg -f avfoundation -list_devices true -i ""
ffmpeg -f avfoundation -i ":0" -c:a aac -f mpegts "srt://LENGUARAZ_HOST:9000?mode=caller"

# Linux (PulseAudio / PipeWire)
ffmpeg -f pulse -i default -c:a aac -f mpegts "srt://LENGUARAZ_HOST:9000?mode=caller"
```

The `source` field takes a single input path or URL, so device capture always goes through
a local ffmpeg that pushes SRT; this also keeps the capture machine and the Lenguaraz server
independent.

### A microphone or line-in on the Lenguaraz host itself

Same as above with `srt://127.0.0.1:9000?mode=caller` on the sending side and
`srt://127.0.0.1:9000?mode=listener` as the stage source. Inside Docker, publish the UDP
port (`- "9000:9000/udp"` in `docker-compose.yml`).

### Interpreter booth or mixer feeds

Give each interpreter channel its own stage (`source_lang: ["es-419"]`, `targets: ["en"]`),
fed by its own SRT port; the audience picks the stage and language on the live captions page.

## Latency tips

- Prefer SRT/RTMP over HLS; every HLS segment is added delay.
- Keep the encoder's audio bitrate modest (64–96 kbps AAC): transcription needs
  intelligibility, not fidelity, and lower bitrates cut packetization delay.
- Send a clean feed: the program mix without music beds if you can. Captions are only as good
  as the audio; `VAD_THRESHOLD` (default 300 RMS) decides what counts as speech.
- Audio only (`-vn` is applied on our side, but not sending video saves bandwidth):
  add `-vn` on the encoder command when possible.
- If captions stall while the speaker talks, see `docs/troubleshooting.md` ("Captions stop").

## Checking a source before the event

```bash
ffmpeg -hide_banner -i "srt://0.0.0.0:9000?mode=listener" -t 5 -f null -   # prints stream info or the error
uv run lenguaraz smoke-stt --sample path/to/clip.wav                          # WER + latency on your own clip (needs a key)
```
