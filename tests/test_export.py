# SPDX-License-Identifier: Apache-2.0
"""Spec 004 — FR-004-01/02, AC-1 (timing), AC-2 (golden renderers), NFR-004-01."""

from __future__ import annotations

import time

import pytest

from lenguaraz.export import (
    TranscriptEntry,
    TranscriptStore,
    format_timestamp,
    to_srt,
    to_txt,
    to_vtt,
)
from lenguaraz.models import CaptionEvent


def caption(
    seq: int, text: str, *, final: bool, lang: str = "en", t_audio: int, original: str | None = None
) -> CaptionEvent:
    return CaptionEvent(
        stage_id="main",
        seq=seq,
        lang=lang,
        source_lang="en",
        is_final=final,
        text=text,
        original=original,
        t_audio_ms=t_audio,
        latency_ms=0,
    )


def test_store_uses_first_partial_as_start_and_final_as_end_for_every_language() -> None:
    store = TranscriptStore()
    store.record(caption(0, "hel", final=False, t_audio=500))
    store.record(caption(0, "hello wor", final=False, t_audio=1200))
    store.record(caption(0, "Hello world.", final=True, t_audio=3400))
    store.record(
        caption(
            0, "[es] Hello world.", final=True, lang="es", t_audio=3400, original="Hello world."
        )
    )
    store.record(
        caption(0, "[es] Hello world.", final=True, lang="es", t_audio=3400)
    )  # duplicate publish
    assert store.languages() == ["en", "es"]
    assert store.entries("en") == [TranscriptEntry(0, "en", "Hello world.", 500, 3400)]
    assert store.entries("es") == [TranscriptEntry(0, "es", "[es] Hello world.", 500, 3400)]
    assert store.counts() == {"en": 1, "es": 1}


def test_store_falls_back_when_no_partial_was_seen_and_never_overlaps() -> None:
    store = TranscriptStore()
    store.record(caption(0, "One.", final=True, t_audio=4000))  # no partial → 3 s before
    store.record(caption(1, "Two.", final=True, t_audio=4200))  # would overlap → starts at 4000
    entries = store.entries("en")
    assert (entries[0].start_ms, entries[0].end_ms) == (1000, 4000)
    assert (entries[1].start_ms, entries[1].end_ms) == (4000, 4500)  # min cue length 500 ms
    store.record(caption(2, "   ", final=True, t_audio=5000))  # degraded/empty: skipped
    assert store.counts() == {"en": 2}


def test_store_is_bounded() -> None:
    store = TranscriptStore(max_entries=3, max_starts=2)
    for seq in range(5):
        store.record(caption(seq, "x", final=False, t_audio=seq * 1000))
        store.record(caption(seq, f"Line {seq}.", final=True, t_audio=seq * 1000 + 900))
    assert [e.seq for e in store.entries("en")] == [2, 3, 4]


def test_renderers_match_golden_strings() -> None:
    entries = [
        TranscriptEntry(0, "en", "Hello world.", 500, 3400),
        TranscriptEntry(1, "en", "Second line,\nwith a break.", 3400, 3_661_010),
    ]
    assert to_srt(entries) == (
        "1\n00:00:00,500 --> 00:00:03,400\nHello world.\n\n"
        "2\n00:00:03,400 --> 01:01:01,010\nSecond line,\nwith a break.\n\n"
    )
    assert to_vtt(entries) == (
        "WEBVTT\n\n"
        "00:00:00.500 --> 00:00:03.400\nHello world.\n\n"
        "00:00:03.400 --> 01:01:01.010\nSecond line,\nwith a break.\n\n"
    )
    assert to_txt(entries) == "[00:00:00] Hello world.\n[00:00:03] Second line,\nwith a break.\n"
    assert format_timestamp(-5, ",") == "00:00:00,000"
    assert to_srt([]) == "" and to_vtt([]) == "WEBVTT\n\n"


def test_render_dispatch_and_errors() -> None:
    store = TranscriptStore()
    with pytest.raises(KeyError):
        store.render("es", "srt")
    store.record(caption(0, "Hi.", final=True, t_audio=1000))
    assert store.render("en", "srt").startswith("1\n")
    assert store.render("en", "vtt").startswith("WEBVTT")
    assert store.render("en", "txt") == "[00:00:00] Hi.\n"
    with pytest.raises(ValueError):
        store.render("en", "docx")
    store.clear()
    assert store.languages() == []


def test_render_is_fast() -> None:
    store = TranscriptStore()
    for seq in range(1800):  # about 60 min x 3 languages
        lang = ("en", "es", "pt")[seq % 3]
        store.record(
            caption(
                seq,
                f"Sentence number {seq} with some words in it.",
                final=True,
                lang=lang,
                t_audio=seq * 2000,
            )
        )
    started = time.perf_counter()
    for lang in ("en", "es", "pt"):
        for fmt in ("srt", "vtt", "txt"):
            store.render(lang, fmt)
    assert time.perf_counter() - started < 0.2
