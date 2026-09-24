# SPDX-License-Identifier: Apache-2.0
"""``make samples``: generate the bundled test audio with Gemini TTS.

The scripts are the reference transcripts in ``samples/*.txt`` (original text written for
this project, Constitution Art. I.8). Each sentence is synthesized separately, trimmed of
leading/trailing silence and joined with a fixed gap, so the exact start and end time of
every sentence is known and written to ``samples/<name>.json``; ``make smoke-stt`` uses
those boundaries to measure true speech-to-caption latency (Art. V).

Output: 16 kHz mono 16-bit WAV (the format the STT engine consumes, GT-3.1). Uses quota.
``--rejoin`` re-cuts existing samples with a different gap without calling the API.
"""

from __future__ import annotations

import argparse
import io as _io
import json
import re
import shutil
import subprocess
import sys
import time
import wave
from array import array
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from lenguaraz.config import ConfigError, load_settings

DEFAULT_TTS_RATE = 24_000  # documented TTS output rate; the mime type is authoritative
OUT_RATE = 16_000
BYTES_PER_MS_OUT = OUT_RATE * 2 // 1000
GAP_MS = 1500  # the server VAD needs a clear pause to finalize a turn (docs/metrics.md)
TRIM_THRESHOLD = 400  # |sample| below this counts as silence (16-bit scale)
TRIM_PAD_MS = 120
MAX_TOTAL_BYTES = 5 * 1024 * 1024  # Constitution Art. XVI
RETRY_DELAYS = (8, 16, 32)  # seconds; 503 "high demand" and 429 are transient
SAMPLES_DIR = Path("samples")
_RATE = re.compile(r"rate=(\d+)")


@dataclass(frozen=True, slots=True)
class SampleSpec:
    name: str
    language: str
    voice: str


@dataclass(frozen=True, slots=True)
class Clip:
    """Raw s16le mono PCM at ``rate`` Hz as returned by the TTS model."""

    pcm: bytes
    rate: int
    mime_type: str = ""


SAMPLES = [
    SampleSpec("en_kubernetes", "en-US", "Kore"),
    SampleSpec("es_asyncio", "es-419", "Aoede"),
]

Synthesizer = Callable[[str, SampleSpec], Clip]


def read_script(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def decode_tts_audio(data: bytes, mime_type: str | None) -> Clip:
    """Turn a TTS ``inline_data`` part into raw PCM + rate.

    ``audio/L16;codec=pcm;rate=N`` is raw PCM (3.8 Flash TTS answers at 48 kHz);
    ``audio/wav`` (3.8 Flash-Lite TTS) carries a RIFF header that the ``wave`` module reads.
    """
    mime = mime_type or ""
    if mime.startswith("audio/wav") or data[:4] == b"RIFF":
        with wave.open(_io.BytesIO(data), "rb") as handle:
            if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
                raise RuntimeError(f"unexpected TTS WAV layout: {handle.getparams()}")
            return Clip(handle.readframes(handle.getnframes()), handle.getframerate(), mime)
    return Clip(data, rate_from_mime(mime), mime)


def rate_from_mime(mime_type: str | None, default: int = DEFAULT_TTS_RATE) -> int:
    """``audio/L16;codec=pcm;rate=24000`` → 24000. Gemini 3.8 TTS models answer at 48 kHz."""
    match = _RATE.search(mime_type or "")
    return int(match.group(1)) if match else default


def resample_to_16k(pcm: bytes, rate: int, ffmpeg_bin: str | None = None) -> bytes:
    """Any rate → 16 kHz mono s16le. ffmpeg when available (proper low-pass), else linear."""
    if rate == OUT_RATE:
        return pcm
    if ffmpeg_bin and shutil.which(ffmpeg_bin):
        args = [ffmpeg_bin, "-hide_banner", "-loglevel", "error"]
        args += ["-f", "s16le", "-ar", str(rate), "-ac", "1", "-i", "pipe:0"]
        args += ["-ar", str(OUT_RATE), "-ac", "1", "-f", "s16le", "pipe:1"]
        return subprocess.run(args, input=pcm, capture_output=True, check=True).stdout
    samples = array("h")
    samples.frombytes(pcm[: len(pcm) - len(pcm) % 2])
    out = array("h")
    ratio = rate / OUT_RATE
    for i in range(int(len(samples) / ratio)):
        pos = i * ratio
        j = int(pos)
        frac = pos - j
        nxt = samples[j + 1] if j + 1 < len(samples) else samples[j]
        out.append(int(samples[j] * (1 - frac) + nxt * frac))
    return out.tobytes()


def resample_24k_to_16k(pcm: bytes, ffmpeg_bin: str | None = None) -> bytes:
    return resample_to_16k(pcm, DEFAULT_TTS_RATE, ffmpeg_bin)


def trim_silence(pcm: bytes, threshold: int = TRIM_THRESHOLD, pad_ms: int = TRIM_PAD_MS) -> bytes:
    """Cut leading/trailing near-silence from 16 kHz s16le audio, keeping a short pad."""
    samples = array("h")
    samples.frombytes(pcm[: len(pcm) - len(pcm) % 2])
    loud = [i for i, value in enumerate(samples) if abs(value) > threshold]
    if not loud:
        return pcm
    pad = pad_ms * OUT_RATE // 1000
    start = max(0, loud[0] - pad)
    end = min(len(samples), loud[-1] + pad)
    return samples[start:end].tobytes()


def join_with_gaps(
    sentences: Sequence[str], clips: Sequence[bytes], gap_ms: int = GAP_MS
) -> tuple[bytes, list[dict[str, object]]]:
    """Concatenate 16 kHz clips with silence; return the PCM and sentence boundaries."""
    gap = bytes(gap_ms * BYTES_PER_MS_OUT)
    parts: list[bytes] = []
    boundaries: list[dict[str, object]] = []
    cursor_ms = 0
    for index, (sentence, clip) in enumerate(zip(sentences, clips, strict=True)):
        duration_ms = len(clip) // BYTES_PER_MS_OUT
        boundaries.append(
            {
                "index": index,
                "text": sentence,
                "start_ms": cursor_ms,
                "end_ms": cursor_ms + duration_ms,
            }
        )
        parts.append(clip)
        parts.append(gap)
        cursor_ms += duration_ms + gap_ms
    return b"".join(parts), boundaries


def write_wav(path: Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(OUT_RATE)
        handle.writeframes(pcm)


def write_meta(json_path: Path, meta: dict[str, object]) -> None:
    text = json.dumps(meta, indent=2, ensure_ascii=False)
    json_path.write_text(text + chr(10), encoding="utf-8")


def build_sample(
    spec: SampleSpec,
    sentences: Sequence[str],
    synthesize: Synthesizer,
    *,
    ffmpeg_bin: str | None,
    model: str,
    out_dir: Path = SAMPLES_DIR,
    gap_ms: int = GAP_MS,
) -> tuple[Path, Path]:
    clips: list[bytes] = []
    mime_types: set[str] = set()
    for text in sentences:
        clip = synthesize(text, spec)
        mime_types.add(f"{clip.mime_type or 'unknown'} ({clip.rate} Hz)")
        clips.append(trim_silence(resample_to_16k(clip.pcm, clip.rate, ffmpeg_bin)))
    pcm, boundaries = join_with_gaps(sentences, clips, gap_ms=gap_ms)
    wav_path = out_dir / f"{spec.name}.wav"
    json_path = out_dir / f"{spec.name}.json"
    write_wav(wav_path, pcm)
    write_meta(
        json_path,
        {
            "sample": spec.name,
            "language": spec.language,
            "voice": spec.voice,
            "model": model,
            "tts_mime_types": sorted(mime_types),
            "sample_rate": OUT_RATE,
            "duration_ms": len(pcm) // BYTES_PER_MS_OUT,
            "gap_ms": gap_ms,
            "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "license": "Apache-2.0",
            "sentences": boundaries,
        },
    )
    return wav_path, json_path


def rejoin_sample(name: str, gap_ms: int, out_dir: Path = SAMPLES_DIR) -> tuple[Path, Path]:
    """Re-cut an existing sample from its JSON boundaries and join it with a new gap (no API)."""
    wav_path = out_dir / f"{name}.wav"
    json_path = out_dir / f"{name}.json"
    meta = json.loads(json_path.read_text(encoding="utf-8"))
    with wave.open(str(wav_path), "rb") as handle:
        pcm = handle.readframes(handle.getnframes())
    sentences = [str(s["text"]) for s in meta["sentences"]]
    clips = [
        pcm[int(s["start_ms"]) * BYTES_PER_MS_OUT : int(s["end_ms"]) * BYTES_PER_MS_OUT]
        for s in meta["sentences"]
    ]
    joined, boundaries = join_with_gaps(sentences, clips, gap_ms=gap_ms)
    write_wav(wav_path, joined)
    meta.update(
        {
            "duration_ms": len(joined) // BYTES_PER_MS_OUT,
            "gap_ms": gap_ms,
            "sentences": boundaries,
            "rejoined_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        }
    )
    write_meta(json_path, meta)
    return wav_path, json_path


def gemini_synthesizer(api_key: str, model: str) -> Synthesizer:
    """TTS through ``models.generate_content`` (speech-generation guide, verified via MCP).

    The text is passed verbatim: any "style" prefix would be read aloud by the model. The
    sample rate comes from ``inline_data.mime_type`` (``audio/L16;codec=pcm;rate=24000``).
    Transient 429/500/503 answers are retried with a fixed backoff.
    """
    from google import genai
    from google.genai import errors, types

    client = genai.Client(api_key=api_key)

    def config(spec: SampleSpec) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            response_modalities=[types.Modality.AUDIO],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=spec.voice)
                )
            ),
        )

    def synthesize(text: str, spec: SampleSpec) -> Clip:
        response = None
        for attempt, delay in enumerate((*RETRY_DELAYS, None)):
            try:
                response = client.models.generate_content(
                    model=model, contents=text, config=config(spec)
                )
                break
            except errors.APIError as exc:
                code = getattr(exc, "code", None)
                if delay is None or code not in (429, 500, 503):
                    raise
                print(f"  {code} from TTS, retry {attempt + 1} in {delay}s…", file=sys.stderr)
                time.sleep(delay)
        assert response is not None
        for candidate in response.candidates or []:
            for part in (candidate.content.parts if candidate.content else None) or []:
                if part.inline_data and part.inline_data.data:
                    return decode_tts_audio(
                        bytes(part.inline_data.data), part.inline_data.mime_type
                    )
        raise RuntimeError(f"TTS returned no audio for: {text[:40]}…")

    return synthesize


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lenguaraz samples")
    parser.add_argument("--only", choices=[s.name for s in SAMPLES], default=None)
    parser.add_argument("--out", default=str(SAMPLES_DIR))
    parser.add_argument("--model", default=None, help="override GEMINI_TTS_MODEL")
    parser.add_argument("--max-sentences", type=int, default=None)
    parser.add_argument("--gap-ms", type=int, default=GAP_MS)
    parser.add_argument(
        "--rejoin", action="store_true", help="re-cut existing samples with --gap-ms (no API)"
    )
    args = parser.parse_args(argv)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.rejoin:
        for spec in SAMPLES:
            if args.only and spec.name != args.only:
                continue
            wav_path, _ = rejoin_sample(spec.name, args.gap_ms, out_dir)
            size = wav_path.stat().st_size
            print(f"  rejoined {wav_path} ({size / 1024:.0f} KB, {size / (OUT_RATE * 2):.1f} s)")
        return 0

    try:
        settings = load_settings()
        api_key = settings.api_key()
    except ConfigError as exc:
        print(f"configuration error: {exc} (samples need a GEMINI_API_KEY)", file=sys.stderr)
        return 2
    model = args.model or settings.gemini_tts_model
    synthesize = gemini_synthesizer(api_key, model)
    total = 0
    for spec in SAMPLES:
        if args.only and spec.name != args.only:
            continue
        script = out_dir / f"{spec.name}.txt"
        if not script.is_file():
            print(f"missing script {script}", file=sys.stderr)
            return 2
        sentences = read_script(script)
        if args.max_sentences:
            sentences = sentences[: args.max_sentences]
        print(f"{spec.name}: synthesizing {len(sentences)} sentences with {spec.voice} ({model})…")
        wav_path, json_path = build_sample(
            spec,
            sentences,
            synthesize,
            ffmpeg_bin=settings.ffmpeg_bin,
            model=model,
            out_dir=out_dir,
            gap_ms=args.gap_ms,
        )
        size = wav_path.stat().st_size
        total += size
        meta = json.loads(json_path.read_text(encoding="utf-8"))
        print(
            f"  wrote {wav_path} ({size / 1024:.0f} KB, {size / (OUT_RATE * 2):.1f} s); "
            f"TTS audio: {', '.join(meta['tts_mime_types'])}"
        )
    if total > MAX_TOTAL_BYTES:
        print(f"samples total {total / 1024 / 1024:.1f} MB exceeds 5 MB", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
