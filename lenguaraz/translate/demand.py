# SPDX-License-Identifier: Apache-2.0
"""Language demand — which languages a stage should translate right now (decision D8).

active = always_on plus the languages that had at least one listener within the grace period,
restricted to the stage's configured targets. Evaluated lazily whenever a caption arrives,
so a new listener is served by the very next final (≤ 500 ms, NFR-002-05) and a language
keeps flowing for ``grace_seconds`` after its last listener leaves (prior art PA-2).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable


class LanguageDemand:
    def __init__(
        self,
        always_on: Iterable[str],
        grace_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._always_on = [code.lower() for code in always_on]
        self._grace = grace_seconds
        self._clock = clock
        self._last_seen: dict[str, float] = {}

    def observe(self, listening: Iterable[str], now: float | None = None) -> None:
        stamp = self._clock() if now is None else now
        for code in listening:
            self._last_seen[code.lower()] = stamp

    def active(
        self, candidates: Iterable[str] | None = None, now: float | None = None
    ) -> list[str]:
        stamp = self._clock() if now is None else now
        allowed = None if candidates is None else {code.lower() for code in candidates}
        result: list[str] = []
        for code in self._always_on:
            if (allowed is None or code in allowed) and code not in result:
                result.append(code)
        for code, seen in sorted(self._last_seen.items()):
            if stamp - seen > self._grace:
                continue
            if (allowed is None or code in allowed) and code not in result:
                result.append(code)
        expired = [code for code, seen in self._last_seen.items() if stamp - seen > self._grace]
        for code in expired:
            del self._last_seen[code]
        return result
