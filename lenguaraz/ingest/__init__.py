# SPDX-License-Identifier: Apache-2.0
"""Audio ingest — files, streams and devices become 16 kHz mono PCM chunks."""

from lenguaraz.ingest.base import (
    BYTES_PER_MS,
    CHUNK_BYTES,
    SAMPLE_RATE,
    AudioSource,
    IngestError,
    open_source,
)

__all__ = [
    "BYTES_PER_MS",
    "CHUNK_BYTES",
    "SAMPLE_RATE",
    "AudioSource",
    "IngestError",
    "open_source",
]
