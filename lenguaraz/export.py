# SPDX-License-Identifier: Apache-2.0
"""Acta — the written record of the parley: transcript store and SRT/VTT/TXT renderers.

The store keeps final captions per language with their position on the audio timeline
(``start_ms`` = first partial of the utterance, ``end_ms`` = its final). It lives in memory,
bounded, and is written to disk only when an operator exports it (Constitution Art. IX.1).
"""

from __future__ import annotations

from collections import OrderedDict, deque
from collections.abc import Sequence
from dataclasses import dataclass

from lenguaraz.models import CaptionEvent

FORMATS = ("srt", "vtt", "txt")
MIN_CUE_MS = 500
FALLBACK_UTTERANCE_MS = 3000


@dataclass(frozen=True, slots=True)
class TranscriptEntry:
    seq: int
    lang: str
    text: str
    start_ms: int
    end_ms: int


class TranscriptStore:
    def __init__(self, max_entries: int = 5000, max_starts: int = 500) -> None:
        self._max_entries = max_entries
        self._max_starts = max_starts
        self._entries: dict[str, deque[TranscriptEntry]] = {}
        self._starts: OrderedDict[int, int] = OrderedDict()
        self._last_end: dict[str, int] = {}

    def record(self, event: CaptionEvent) -> None:
        if not event.is_final:
            if event.seq not in self._starts:
                self._starts[event.seq] = event.t_audio_ms
                while len(self._starts) > self._max_starts:
                    self._starts.popitem(last=False)
            return
        text = event.text.strip()
        if not text:
            return  # degraded translations carry no text; the original language keeps the line
        entries = self._entries.setdefault(event.lang, deque(maxlen=self._max_entries))
        if entries and entries[-1].seq == event.seq:
            return  # already recorded for this language
        prev_end = self._last_end.get(event.lang, 0)
        start = self._starts.get(event.seq)
        if start is None:
            start = max(prev_end, event.t_audio_ms - FALLBACK_UTTERANCE_MS)
        start = max(start, prev_end)
        end = max(event.t_audio_ms, start + MIN_CUE_MS)
        entries.append(TranscriptEntry(event.seq, event.lang, text, start, end))
        self._last_end[event.lang] = end

    def languages(self) -> list[str]:
        return sorted(lang for lang, entries in self._entries.items() if entries)

    def entries(self, lang: str) -> list[TranscriptEntry]:
        return list(self._entries.get(lang, ()))

    def counts(self) -> dict[str, int]:
        return {lang: len(entries) for lang, entries in self._entries.items() if entries}

    def render(self, lang: str, fmt: str) -> str:
        if lang not in self._entries or not self._entries[lang]:
            raise KeyError(lang)
        entries = self.entries(lang)
        if fmt == "srt":
            return to_srt(entries)
        if fmt == "vtt":
            return to_vtt(entries)
        if fmt == "txt":
            return to_txt(entries)
        raise ValueError(fmt)

    def clear(self) -> None:
        self._entries.clear()
        self._starts.clear()
        self._last_end.clear()


def format_timestamp(ms: int, separator: str) -> str:
    ms = max(0, ms)
    hours, rest = divmod(ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, millis = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{millis:03d}"


def to_srt(entries: Sequence[TranscriptEntry]) -> str:
    blocks = []
    for index, e in enumerate(entries, start=1):
        span = f"{format_timestamp(e.start_ms, ',')} --> {format_timestamp(e.end_ms, ',')}"
        blocks.append(f"{index}\n{span}\n{e.text}\n")
    return "\n".join(blocks) + ("\n" if blocks else "")


def to_vtt(entries: Sequence[TranscriptEntry]) -> str:
    blocks = [
        f"{format_timestamp(e.start_ms, '.')} --> {format_timestamp(e.end_ms, '.')}\n{e.text}\n"
        for e in entries
    ]
    return "WEBVTT\n\n" + "\n".join(blocks) + ("\n" if blocks else "")


def to_txt(entries: Sequence[TranscriptEntry]) -> str:
    return "".join(f"[{format_timestamp(e.start_ms, '.')[:8]}] {e.text}\n" for e in entries)
