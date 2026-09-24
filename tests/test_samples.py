# SPDX-License-Identifier: Apache-2.0
"""Spec 001 — FR-001-12, AC-12: bundled samples and the generator's pure parts."""

from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path

from lenguaraz.tools.samples import (
    GAP_MS,
    OUT_RATE,
    SAMPLES,
    Clip,
    SampleSpec,
    build_sample,
    decode_tts_audio,
    join_with_gaps,
    rate_from_mime,
    read_script,
    resample_24k_to_16k,
)

ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = ROOT / "samples"


def sine_pcm(rate: int, seconds: float, freq: float = 440.0) -> bytes:
    n = int(rate * seconds)
    return b"".join(
        struct.pack("<h", int(6000 * math.sin(2 * math.pi * freq * i / rate))) for i in range(n)
    )


def test_bundled_samples_are_16k_mono_and_small() -> None:
    total = 0
    for spec in SAMPLES:
        wav_path = SAMPLES_DIR / f"{spec.name}.wav"
        txt_path = SAMPLES_DIR / f"{spec.name}.txt"
        assert wav_path.is_file() and txt_path.is_file(), spec.name
        with wave.open(str(wav_path), "rb") as handle:
            assert handle.getframerate() == OUT_RATE
            assert handle.getnchannels() == 1
            assert handle.getsampwidth() == 2
            seconds = handle.getnframes() / OUT_RATE
        assert 5 <= seconds <= 120
        assert len(read_script(txt_path)) >= 5
        total += wav_path.stat().st_size
        json_path = SAMPLES_DIR / f"{spec.name}.json"
        if json_path.is_file():  # real TTS samples carry sentence boundaries
            meta = json.loads(json_path.read_text(encoding="utf-8"))
            assert 30 <= seconds <= 120, "TTS samples should be 30-120 s"
            assert meta["sample_rate"] == OUT_RATE
            assert [s["text"] for s in meta["sentences"]] == read_script(txt_path)
            assert meta["sentences"][-1]["end_ms"] <= meta["duration_ms"]
    assert total < 5 * 1024 * 1024


def test_rate_from_mime() -> None:
    assert rate_from_mime("audio/L16;codec=pcm;rate=24000") == 24000
    assert rate_from_mime("audio/L16;codec=pcm;rate=48000") == 48000
    assert rate_from_mime(None) == 24000


def test_decode_tts_audio_handles_raw_pcm_and_wav(tmp_path: Path) -> None:
    raw = decode_tts_audio(b"\x01\x00" * 10, "audio/L16;codec=pcm;rate=48000")
    assert raw.rate == 48000 and len(raw.pcm) == 20
    path = tmp_path / "tts.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(b"\x02\x00" * 5)
    clip = decode_tts_audio(path.read_bytes(), "audio/wav")
    assert clip.rate == 24000 and clip.pcm == b"\x02\x00" * 5


def test_resample_halves_length_ratio_and_keeps_signal() -> None:
    pcm24 = sine_pcm(24_000, 0.5)
    pcm16 = resample_24k_to_16k(pcm24, ffmpeg_bin=None)
    assert abs(len(pcm16) - len(pcm24) * 2 / 3) < 8
    peak = max(abs(v) for v in struct.unpack(f"<{len(pcm16) // 2}h", pcm16))
    assert 5000 <= peak <= 6000


def test_join_with_gaps_records_sentence_boundaries() -> None:
    clips = [bytes(32 * 1000), bytes(32 * 1500)]  # 1.0 s and 1.5 s at 16 kHz
    pcm, boundaries = join_with_gaps(["One.", "Two."], clips)
    assert len(pcm) == 32 * (1000 + GAP_MS + 1500 + GAP_MS)
    assert boundaries == [
        {"index": 0, "text": "One.", "start_ms": 0, "end_ms": 1000},
        {"index": 1, "text": "Two.", "start_ms": 1000 + GAP_MS, "end_ms": 1000 + GAP_MS + 1500},
    ]


def test_build_sample_writes_wav_and_json_without_network(tmp_path: Path) -> None:
    spec = SampleSpec("unit", "en-US", "Kore")
    calls: list[str] = []

    def fake_synth(text: str, _spec: SampleSpec) -> Clip:
        calls.append(text)
        return Clip(sine_pcm(24_000, 0.3), 24_000, "audio/L16;codec=pcm;rate=24000")

    wav_path, json_path = build_sample(
        spec, ["Alpha.", "Beta."], fake_synth, ffmpeg_bin=None, model="tts-x", out_dir=tmp_path
    )
    assert calls == ["Alpha.", "Beta."]
    with wave.open(str(wav_path), "rb") as handle:
        assert handle.getframerate() == OUT_RATE and handle.getnchannels() == 1
        assert abs(handle.getnframes() / OUT_RATE - (0.3 + GAP_MS / 1000) * 2) < 0.02
    meta = json.loads(json_path.read_text(encoding="utf-8"))
    assert meta["model"] == "tts-x" and meta["license"] == "Apache-2.0"
    assert len(meta["sentences"]) == 2 and meta["sentences"][1]["start_ms"] == 300 + GAP_MS
