# SPDX-License-Identifier: Apache-2.0
"""Per-stage latency window and counters (Constitution Art. V.1)."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

WINDOW = 200


def percentile(values: list[int], p: float) -> int:
    """Nearest-rank percentile; 0 for an empty list."""
    if not values:
        return 0
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100.0 * len(ordered)))
    return ordered[rank - 1]


class LatencyWindow:
    def __init__(self, size: int = WINDOW) -> None:
        self._values: deque[int] = deque(maxlen=size)

    def add(self, latency_ms: int) -> None:
        self._values.append(latency_ms)

    def __len__(self) -> int:
        return len(self._values)

    @property
    def p50(self) -> int:
        return percentile(list(self._values), 50)

    @property
    def p95(self) -> int:
        return percentile(list(self._values), 95)


@dataclass(slots=True)
class StageMetrics:
    """What the ``metrics`` event and the admin view read."""

    finals: LatencyWindow = field(default_factory=LatencyWindow)
    interims: LatencyWindow = field(default_factory=LatencyWindow)
    captions_final: int = 0
    captions_interim: int = 0

    def record(self, latency_ms: int, *, is_final: bool) -> None:
        if is_final:
            self.captions_final += 1
            self.finals.add(latency_ms)
        else:
            self.captions_interim += 1
            self.interims.add(latency_ms)
