# SPDX-License-Identifier: Apache-2.0
"""ffmpeg subprocess source: any file, HLS, RTMP, SRT or device → s16le mono 16 kHz.

ffmpeg is invoked as a separate program and never linked (Constitution Art. XVII.B.4).
One process per stage; it is terminated on close and killed if it does not exit.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from pathlib import Path

from lenguaraz.ingest.base import CHUNK_BYTES, IngestError

KILL_AFTER_SECONDS = 2.0
STDERR_TAIL_BYTES = 2_000


def build_ffmpeg_args(
    source: str, *, ffmpeg_bin: str = "ffmpeg", realtime: bool = True, loop: bool = False
) -> list[str]:
    """Command line that decodes ``source`` to raw PCM on stdout."""
    args = [ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-nostdin"]
    local_file = "://" not in source and Path(source).suffix != ""
    if realtime and local_file:
        args.append("-re")  # replay files at their natural speed
    if loop and local_file:
        args += ["-stream_loop", "-1"]
    args += [
        "-i",
        source,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-acodec",
        "pcm_s16le",
        "-f",
        "s16le",
        "pipe:1",
    ]
    return args


class FfmpegSource:
    def __init__(
        self,
        source: str,
        *,
        ffmpeg_bin: str = "ffmpeg",
        realtime: bool = True,
        loop: bool = False,
        chunk_bytes: int = CHUNK_BYTES,
    ) -> None:
        self._source = source
        self._args = build_ffmpeg_args(source, ffmpeg_bin=ffmpeg_bin, realtime=realtime, loop=loop)
        self._chunk_bytes = chunk_bytes
        self._process: asyncio.subprocess.Process | None = None
        self._closed = False

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process else None

    async def chunks(self) -> AsyncIterator[bytes]:
        try:
            self._process = await asyncio.create_subprocess_exec(
                *self._args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )
        except FileNotFoundError as exc:
            raise IngestError(
                f"ffmpeg not found ({self._args[0]}); install it or set FFMPEG_BIN"
            ) from exc
        process = self._process
        assert process.stdout is not None
        try:
            while not self._closed:
                try:
                    data = await process.stdout.readexactly(self._chunk_bytes)
                except asyncio.IncompleteReadError as exc:
                    if exc.partial:
                        yield exc.partial + bytes(self._chunk_bytes - len(exc.partial))
                    break
                yield data
            if not self._closed:
                await process.wait()
                if process.returncode not in (0, None):
                    raise IngestError(
                        f"ffmpeg exited with {process.returncode} for {self._source}: "
                        f"{await self._stderr_tail()}"
                    )
        finally:
            await self.close()

    async def _stderr_tail(self) -> str:
        if self._process is None or self._process.stderr is None:
            return ""
        with contextlib.suppress(Exception):
            data = await asyncio.wait_for(self._process.stderr.read(), 1.0)
            return data[-STDERR_TAIL_BYTES:].decode("utf-8", "replace").strip()
        return ""

    async def close(self) -> None:
        self._closed = True
        process = self._process
        if process is None or process.returncode is not None:
            return
        with contextlib.suppress(ProcessLookupError):
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), KILL_AFTER_SECONDS)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            with contextlib.suppress(Exception):
                await process.wait()
