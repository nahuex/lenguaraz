# SPDX-License-Identifier: Apache-2.0
"""``make loadtest``: viewer fan-out load test on the caption WebSocket (spec 005 follow-up).

The server runs as a subprocess with the fake engine (no credentials, no quota). For every
step in ``--viewers`` the tool opens that many WebSocket viewers with the ``websockets``
client, holds them for ``--seconds`` and measures the *fan-out spread*: the wall time between
the first and the last viewer receiving the same caption event. Server CPU and RSS come from
``psutil`` sampled on the server process. The report states what was measured and how
(Constitution Art. VII.4, Art. XIV).
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import platform
import signal
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any

from lenguaraz.config import ConfigError, StagesFile
from lenguaraz.metrics import percentile

REPORT_MD = Path("docs/loadtest-report.md")
REPORT_JSON = Path("docs/loadtest-report.json")
SCALE_REPORT_MD = Path("docs/scale-report.md")
FANOUT_HEADING = "## Viewer fan-out"
DEFAULT_VIEWERS = "100,500,1000"
SERVER_ENV = {
    "ENGINE": "fake",
    "WS_MAX_CONN_PER_IP": "1000000",
    "LOG_LEVEL": "WARNING",
}
HEALTH_TIMEOUT_SECONDS = 60.0
STOP_TIMEOUT_SECONDS = 10.0

# (stage_id, lang, seq, is_final, text): interims share ``seq`` with their final, so the
# text is part of the identity; for finals the key is equivalent to (seq, is_final).
EventKey = tuple[str, str, int, bool, str]


# --------------------------------------------------------------------------- pure parts


@dataclass(slots=True)
class SpreadStats:
    events: int  # distinct caption events seen inside the measurement window
    complete: int  # events received by every connected viewer
    basis: str  # "complete" (preferred) or "partial" (events seen by >= 2 viewers)
    p50_ms: int
    p95_ms: int
    max_ms: int
    coverage_median: float  # median fraction of connected viewers that received an event


def compute_spread(
    receipts: Mapping[Any, Sequence[float]], connected: int | Mapping[tuple[str, str], int]
) -> SpreadStats:
    """Fan-out spread per event = last receive time - first receive time, in ms.

    ``connected`` is the number of viewers that should receive each event: one total, or a
    mapping per (stage, lang) target when viewers are spread over several stages (a viewer
    on another stage never sees the event). Percentiles are taken over the events every
    such viewer received ("complete"); events at the window edges or dropped for a slow
    viewer are incomplete and only used when no event is complete, so a partial view never
    makes the number look better.
    """
    complete: list[int] = []
    partial: list[int] = []
    coverage: list[float] = []
    for key, times in receipts.items():
        expected = connected if isinstance(connected, int) else connected.get(tuple(key[:2]), 0)
        coverage.append(len(times) / expected if expected else 0.0)
        if len(times) < 2:
            continue
        spread_ms = round((max(times) - min(times)) * 1000)
        if expected and len(times) >= expected:
            complete.append(spread_ms)
        else:
            partial.append(spread_ms)
    values = complete or partial
    return SpreadStats(
        events=len(receipts),
        complete=len(complete),
        basis="complete" if complete else "partial",
        p50_ms=percentile(values, 50),
        p95_ms=percentile(values, 95),
        max_ms=max(values) if values else 0,
        coverage_median=round(statistics.median(coverage), 3) if coverage else 0.0,
    )


def parse_viewers(text: str) -> list[int]:
    """``"100,500,1000"`` -> ``[100, 500, 1000]``; every step must be a positive integer."""
    steps: list[int] = []
    for raw in text.split(","):
        raw = raw.strip()
        if not raw:
            continue
        if not raw.isdigit() or int(raw) == 0:
            raise argparse.ArgumentTypeError(f"--viewers expects positive integers, got {raw!r}")
        steps.append(int(raw))
    if not steps:
        raise argparse.ArgumentTypeError("--viewers needs at least one step, e.g. 100,500")
    return steps


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lenguaraz loadtest")
    parser.add_argument(
        "--viewers",
        type=parse_viewers,
        default=parse_viewers(DEFAULT_VIEWERS),
        help=f"comma-separated viewer counts, one step each (default {DEFAULT_VIEWERS})",
    )
    parser.add_argument("--seconds", type=float, default=30.0, help="hold time per step")
    parser.add_argument(
        "--stages", type=int, default=1, help="spread the viewers across the first N stages"
    )
    parser.add_argument("--stages-file", default="stages.yaml")
    parser.add_argument("--port", type=int, default=0, help="server port (0 = a free port)")
    parser.add_argument(
        "--connect-concurrency", type=int, default=100, help="parallel connection attempts"
    )
    parser.add_argument("--out", default=REPORT_MD.as_posix())
    parser.add_argument(
        "--scale-report",
        default=SCALE_REPORT_MD.as_posix(),
        help=f'scale report to update with a "{FANOUT_HEADING}" section ("" = skip)',
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def upsert_section(text: str, heading: str, body: str) -> str:
    """Replace the ``heading`` section (up to the next ``## `` heading) or append it."""
    block = f"{heading}\n\n{body.strip()}\n"
    lines = text.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if line.rstrip("\n") == heading), None)
    if start is None:
        base = text if not text or text.endswith("\n") else text + "\n"
        return f"{base}\n{block}" if base else block
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    tail = "".join(lines[end:])
    return "".join(lines[:start]) + block + ("\n" + tail if tail else "")


def extract_section(text: str, heading: str) -> str | None:
    """The body of the ``heading`` section, or None when the document has none."""
    lines = text.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if line.rstrip("\n") == heading), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "".join(lines[start + 1 : end]).strip()


# --------------------------------------------------------------------------- report


@dataclass(slots=True)
class StepResult:
    viewers: int
    stages: int
    connected: int
    failed: int
    disconnected: int
    connect_seconds: float
    hold_seconds: float
    close_seconds: float
    events_total: int
    events_complete: int
    spread_basis: str
    coverage_median: float
    events_per_client_min: int
    events_per_client_median: int
    caption_msgs_per_second: float
    spread_p50_ms: int
    spread_p95_ms: int
    spread_max_ms: int
    server_cpu_avg_percent: float | None
    server_cpu_max_percent: float | None
    server_rss_start_mb: float | None
    server_rss_end_mb: float | None
    server_rss_delta_mb: float | None
    client_cpu_avg_percent: float | None
    client_cpu_max_percent: float | None
    failures: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class Report:
    generated_at: str
    machine: str
    engine: str
    stage_ids: list[str]
    seconds: float
    steps: list[StepResult]
    honesty: str


def _fmt(value: float | int | None, suffix: str = "") -> str:
    return "n/a" if value is None else f"{value}{suffix}"


def render_markdown(report: Report) -> str:
    columns = [
        "Viewers",
        "Connected / failed / dropped",
        "Events per viewer (min / median)",
        "Spread p50 / p95 / max ms",
        "Complete events",
        "Server CPU avg / max %",
        "Server RSS start -> end (delta) MB",
        "Client CPU avg / max %",
        "Msgs/s received",
    ]
    lines = [
        "# Viewer fan-out load test",
        "",
        f"Generated by `make loadtest` (spec 005 follow-up) on {report.generated_at}. "
        f"{report.honesty}",
        "",
        "## Results",
        "",
        "| " + " | ".join(columns) + " |",
        "|" + "---|" * len(columns),
    ]
    for step in report.steps:
        cells = [
            f"{step.viewers} on {step.stages} stage(s)",
            f"{step.connected} / {step.failed} / {step.disconnected}",
            f"{step.events_per_client_min} / {step.events_per_client_median}",
            f"{step.spread_p50_ms} / {step.spread_p95_ms} / {step.spread_max_ms}",
            f"{step.events_complete} of {step.events_total} ({step.spread_basis})",
            f"{_fmt(step.server_cpu_avg_percent)} / {_fmt(step.server_cpu_max_percent)}",
            f"{_fmt(step.server_rss_start_mb)} -> {_fmt(step.server_rss_end_mb)} "
            f"({_fmt(step.server_rss_delta_mb)})",
            f"{_fmt(step.client_cpu_avg_percent)} / {_fmt(step.client_cpu_max_percent)}",
            f"{step.caption_msgs_per_second}",
        ]
        lines.append("| " + " | ".join(cells) + " |")
    failures = [(step.viewers, step.failures) for step in report.steps if step.failures]
    if failures:
        lines += ["", "Connection failures by cause:", ""]
        for viewers, causes in failures:
            for cause, count in sorted(causes.items(), key=lambda item: -item[1]):
                lines.append(f"- {viewers} viewers: {count} x `{cause}`")
    lines += [
        "",
        "## Method",
        "",
        "- The server is `lenguaraz serve` (same interpreter as `uv run`) started as a",
        "  subprocess with `ENGINE=fake`, `WS_MAX_CONN_PER_IP=1000000`, `LOG_LEVEL=WARNING`",
        f"  and the bundled stages file (stages used: {', '.join(report.stage_ids)}).",
        "- Every step opens its viewers on `ws://127.0.0.1:<port>/ws/<stage>?lang=<source>`",
        "  (round-robin over the stages), waits until every connection is settled, then",
        f"  measures for {report.seconds} s and closes them all; the next step starts fresh.",
        "- Spread = wall time between the first and the last viewer receiving the same",
        "  caption event (identity: stage, language, `seq`, `is_final`, text), recorded in",
        "  the client process with `time.perf_counter()`; p50/p95/max over the events that",
        '  every connected viewer received ("complete"), so edge and dropped events cannot',
        "  flatter the number. Coverage = median share of viewers that received an event.",
        "- Events per viewer = caption messages received inside the window; status and",
        "  metrics events are excluded. Dropped = viewers whose socket closed mid-window.",
        "- Server CPU (% of one core, can exceed 100 with threads) and RSS are sampled once",
        "  per second with `psutil` on the server process; client CPU is the load-test",
        "  process itself, which parses every frame of every viewer.",
        "",
    ]
    return "\n".join(lines)


def scale_report_section(report: Report, report_path: str = "loadtest-report.md") -> str:
    """The body of the ``## Viewer fan-out`` section for ``docs/scale-report.md``."""
    lines = [
        f"Measured by `make loadtest` on {report.generated_at} ({report.machine}); the full "
        f"table, method and honesty note are in [`{report_path}`]({report_path}).",
        "",
        "| Viewers | Connected | Spread p50 / p95 ms | Server CPU avg / max % "
        "| Server RSS delta MB |",
        "|---|---|---|---|---|",
    ]
    for step in report.steps:
        lines.append(
            f"| {step.viewers} | {step.connected} | {step.spread_p50_ms} / {step.spread_p95_ms} "
            f"| {_fmt(step.server_cpu_avg_percent)} / {_fmt(step.server_cpu_max_percent)} "
            f"| {_fmt(step.server_rss_delta_mb)} |"
        )
    lines += ["", report.honesty]
    return "\n".join(lines)


def write_report(report: Report, out_md: Path = REPORT_MD, out_json: Path = REPORT_JSON) -> None:
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(report), encoding="utf-8")
    out_json.write_text(json.dumps(asdict(report), indent=2) + "\n", encoding="utf-8")


def update_scale_report(report: Report, scale_report: Path, out_md: Path) -> None:
    text = scale_report.read_text(encoding="utf-8") if scale_report.is_file() else ""
    try:
        relative = out_md.resolve().relative_to(scale_report.resolve().parent).as_posix()
    except ValueError:
        relative = out_md.as_posix()
    body = scale_report_section(report, relative)
    scale_report.parent.mkdir(parents=True, exist_ok=True)
    scale_report.write_text(upsert_section(text, FANOUT_HEADING, body), encoding="utf-8")


# --------------------------------------------------------------------------- server


def pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class ServerProcess:
    """``lenguaraz serve`` as a child process: start, wait for ``/healthz``, stop cleanly."""

    def __init__(self, port: int, stages_file: Path, env: Mapping[str, str] | None = None):
        self.port = port
        self.stages_file = stages_file
        self.env = dict(SERVER_ENV, **(env or {}))
        self.process: subprocess.Popen[bytes] | None = None
        self._log: IO[bytes] | None = None

    @property
    def pid(self) -> int | None:
        return self.process.pid if self.process is not None else None

    def _descendants(self) -> list[Any]:
        if self.process is None:
            return []
        with contextlib.suppress(Exception):  # psutil is optional
            import psutil

            return list(psutil.Process(self.process.pid).children(recursive=True))
        return []

    def worker_pid(self) -> int | None:
        """PID of the interpreter that serves requests.

        On Windows the virtualenv's ``python.exe`` is a launcher that runs the real
        interpreter as a child, so sampling the launcher would show an idle 14 MB stub;
        the deepest descendant is the server. Without psutil (or children) it is the pid.
        """
        descendants = self._descendants()
        return int(descendants[-1].pid) if descendants else self.pid

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        env = dict(os.environ, **self.env, STAGES_FILE=str(self.stages_file))
        env.pop("PORT", None)
        env.pop("HOST", None)
        self._log = tempfile.TemporaryFile()  # noqa: SIM115 - lives as long as the child
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "lenguaraz.cli",
                "serve",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
            ],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=self._log,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )

    def wait_healthy(self, timeout_seconds: float = HEALTH_TIMEOUT_SECONDS) -> dict[str, Any]:
        if self.process is None:
            raise RuntimeError("server not started")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(
                    f"server exited with code {self.process.returncode} before /healthz "
                    f"answered:\n{self.log_tail()}"
                )
            try:
                with opener.open(f"{self.base_url}/healthz", timeout=1.0) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    if payload.get("status") == "ok":
                        return dict(payload)
            except (urllib.error.URLError, OSError, ValueError):
                pass
            time.sleep(0.2)
        raise RuntimeError(
            f"server did not answer /healthz within {timeout_seconds:.0f}s:\n{self.log_tail()}"
        )

    def stop(self) -> None:
        process = self.process
        if process is None:
            return
        descendants = self._descendants()  # the real interpreter behind a launcher, if any
        if process.poll() is None:
            ctrl_break = getattr(signal, "CTRL_BREAK_EVENT", None)
            with contextlib.suppress(OSError, ValueError):
                if ctrl_break is not None:  # Windows: uvicorn handles SIGBREAK gracefully
                    process.send_signal(ctrl_break)  # reaches the whole process group
                else:
                    process.terminate()
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(STOP_TIMEOUT_SECONDS)
        for harder in ("terminate", "kill"):
            if process.poll() is not None:
                break
            getattr(process, harder)()
            for kid in descendants:
                with contextlib.suppress(Exception):
                    getattr(kid, harder)()
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(STOP_TIMEOUT_SECONDS)
        for kid in descendants:  # never leave the server running behind a dead launcher
            with contextlib.suppress(Exception):
                if kid.is_running():
                    kid.kill()
        if self._log is not None:
            self._log.close()
            self._log = None

    def log_tail(self, lines: int = 20) -> str:
        if self._log is None:
            return ""
        with contextlib.suppress(OSError, ValueError):
            self._log.seek(0)
            text = self._log.read().decode("utf-8", errors="replace")
            return "\n".join(text.splitlines()[-lines:])
        return ""


# --------------------------------------------------------------------------- viewers


@dataclass(slots=True)
class _Window:
    start: float | None = None
    end: float | None = None


@dataclass(slots=True)
class _Viewer:
    index: int
    url: str
    stage_id: str
    lang: str
    state: str = "pending"  # pending | connected | failed | disconnected
    error: str = ""
    events: int = 0


class _Sampler:
    """psutil CPU/RSS sampling for the server and the client process (n/a when missing)."""

    def __init__(self, server_pid: int | None) -> None:
        self.server: Any = None
        self.client: Any = None
        self.server_cpu: list[float] = []
        self.client_cpu: list[float] = []
        self.rss_start: float | None = None
        self.rss_end: float | None = None
        with contextlib.suppress(Exception):  # psutil is optional
            import psutil

            self.client = psutil.Process(os.getpid())
            self.client.cpu_percent(None)
            if server_pid is not None:
                self.server = psutil.Process(server_pid)
                self.server.cpu_percent(None)

    def mark_start(self) -> None:
        if self.server is not None:
            with contextlib.suppress(Exception):
                self.rss_start = round(self.server.memory_info().rss / 1e6, 1)

    def prime_cpu(self) -> None:
        """Reset the CPU counters so the first sample covers the window only."""
        if self.server is not None:
            with contextlib.suppress(Exception):
                self.server.cpu_percent(None)
                self.client.cpu_percent(None)

    def sample(self) -> None:
        if self.server is not None:
            with contextlib.suppress(Exception):
                self.server_cpu.append(self.server.cpu_percent(None))
                self.client_cpu.append(self.client.cpu_percent(None))

    def mark_end(self) -> None:
        if self.server is not None:
            with contextlib.suppress(Exception):
                self.rss_end = round(self.server.memory_info().rss / 1e6, 1)


def _avg_max(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    return round(sum(values) / len(values), 1), round(max(values), 1)


async def _run_viewer(
    viewer: _Viewer,
    gate: asyncio.Semaphore,
    window: _Window,
    receipts: dict[EventKey, list[float]],
    settled: asyncio.Event,
    pending: list[int],
) -> None:
    from websockets.asyncio.client import connect

    def settle() -> None:
        pending[0] -= 1
        if pending[0] <= 0:
            settled.set()

    connection = None
    try:
        async with gate:
            try:
                connection = await connect(
                    viewer.url,
                    proxy=None,  # never route loopback through a corporate proxy
                    ping_interval=None,
                    open_timeout=20,
                    close_timeout=2,
                )
            except Exception as exc:
                viewer.state = "failed"
                viewer.error = f"{type(exc).__name__}: {exc}"[:120]
        if connection is not None:
            viewer.state = "connected"
    finally:
        settle()
    if connection is None:
        return
    try:
        async with connection:
            async for message in connection:
                now = time.perf_counter()
                start = window.start
                if start is None or now < start or (window.end is not None and now > window.end):
                    continue
                event = json.loads(message)
                if event.get("type") != "caption":
                    continue
                key: EventKey = (
                    viewer.stage_id,
                    event["lang"],
                    int(event["seq"]),
                    bool(event["is_final"]),
                    event["text"],
                )
                receipts.setdefault(key, []).append(now)
                viewer.events += 1
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        viewer.state = "disconnected"
        viewer.error = f"{type(exc).__name__}: {exc}"[:120]


async def run_step(
    *,
    targets: Sequence[tuple[str, str]],
    viewers: int,
    seconds: float,
    port: int,
    server_pid: int | None,
    connect_concurrency: int = 100,
) -> StepResult:
    """Open ``viewers`` sockets round-robin over ``targets`` (stage, lang), hold, measure."""
    records: list[_Viewer] = []
    for index in range(viewers):
        stage, lang = targets[index % len(targets)]
        url = f"ws://127.0.0.1:{port}/ws/{stage}?lang={lang}"
        records.append(_Viewer(index=index, url=url, stage_id=stage, lang=lang))
    window = _Window()
    receipts: dict[EventKey, list[float]] = {}
    settled = asyncio.Event()
    pending = [viewers]
    gate = asyncio.Semaphore(max(1, connect_concurrency))
    sampler = _Sampler(server_pid)
    sampler.mark_start()  # RSS baseline before this step's sockets exist

    connect_started = time.monotonic()
    tasks = [
        asyncio.create_task(_run_viewer(v, gate, window, receipts, settled, pending))
        for v in records
    ]
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(settled.wait(), timeout=60.0 + viewers / 20)
    connect_seconds = time.monotonic() - connect_started
    for viewer in records:
        if viewer.state == "pending":
            viewer.state = "failed"
            viewer.error = "TimeoutError: still connecting when the connect phase ended"

    sampler.prime_cpu()
    window.start = time.perf_counter()
    hold_started = time.monotonic()
    while True:
        remaining = seconds - (time.monotonic() - hold_started)
        if remaining <= 0:
            break
        await asyncio.sleep(min(1.0, remaining))
        sampler.sample()
    window.end = time.perf_counter()
    hold_seconds = time.monotonic() - hold_started
    sampler.mark_end()

    close_started = time.monotonic()
    for task in tasks:
        task.cancel()
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=30.0)
    close_seconds = time.monotonic() - close_started

    connected = [v for v in records if v.state == "connected"]
    stats = compute_spread(receipts, Counter((v.stage_id, v.lang) for v in connected))
    counts = sorted(v.events for v in connected)
    failures: dict[str, int] = {}
    for viewer in records:
        if viewer.state in {"failed", "disconnected"}:
            cause = viewer.error.split(":", 1)[0] or "unknown"
            failures[cause] = failures.get(cause, 0) + 1
    cpu_avg, cpu_max = _avg_max(sampler.server_cpu)
    client_avg, client_max = _avg_max(sampler.client_cpu)
    rss_delta = (
        round(sampler.rss_end - sampler.rss_start, 1)
        if sampler.rss_start is not None and sampler.rss_end is not None
        else None
    )
    total_msgs = sum(counts)
    return StepResult(
        viewers=viewers,
        stages=len(targets),
        connected=len(connected),
        failed=sum(1 for v in records if v.state == "failed"),
        disconnected=sum(1 for v in records if v.state == "disconnected"),
        connect_seconds=round(connect_seconds, 2),
        hold_seconds=round(hold_seconds, 1),
        close_seconds=round(close_seconds, 2),
        events_total=stats.events,
        events_complete=stats.complete,
        spread_basis=stats.basis,
        coverage_median=stats.coverage_median,
        events_per_client_min=counts[0] if counts else 0,
        events_per_client_median=int(statistics.median(counts)) if counts else 0,
        caption_msgs_per_second=round(total_msgs / hold_seconds, 1) if hold_seconds else 0.0,
        spread_p50_ms=stats.p50_ms,
        spread_p95_ms=stats.p95_ms,
        spread_max_ms=stats.max_ms,
        server_cpu_avg_percent=cpu_avg,
        server_cpu_max_percent=cpu_max,
        server_rss_start_mb=sampler.rss_start,
        server_rss_end_mb=sampler.rss_end,
        server_rss_delta_mb=rss_delta,
        client_cpu_avg_percent=client_avg,
        client_cpu_max_percent=client_max,
        failures=failures,
    )


async def _run_steps(
    targets: Sequence[tuple[str, str]],
    steps: Sequence[int],
    seconds: float,
    port: int,
    server_pid: int | None,
    connect_concurrency: int,
) -> list[StepResult]:
    results: list[StepResult] = []
    for index, viewers in enumerate(steps):
        if index:
            await asyncio.sleep(2.0)  # let the server release the previous step's sockets
        print(f"loadtest: step {viewers} viewers x {seconds:.0f}s ...", flush=True)
        result = await run_step(
            targets=targets,
            viewers=viewers,
            seconds=seconds,
            port=port,
            server_pid=server_pid,
            connect_concurrency=connect_concurrency,
        )
        print(
            f"loadtest: {result.connected}/{viewers} connected, spread p50/p95 "
            f"{result.spread_p50_ms}/{result.spread_p95_ms} ms, server CPU avg "
            f"{_fmt(result.server_cpu_avg_percent, '%')}",
            flush=True,
        )
        results.append(result)
    return results


def stage_targets(stages_file: Path, stages: int) -> list[tuple[str, str]]:
    """(stage id, language) pairs for the first ``stages`` stages: their source language."""
    loaded = StagesFile.load(stages_file)
    if stages < 1 or stages > len(loaded.stages):
        raise ConfigError(
            f"--stages must be between 1 and {len(loaded.stages)} (stages in {stages_file})"
        )
    return [
        (stage.id, stage.primary_source_lang or stage.languages()[0])
        for stage in loaded.stages[:stages]
    ]


def run_loadtest(
    *,
    viewers: Sequence[int],
    seconds: float,
    stages: int = 1,
    stages_file: Path = Path("stages.yaml"),
    port: int = 0,
    connect_concurrency: int = 100,
) -> Report:
    targets = stage_targets(stages_file, stages)
    server = ServerProcess(port or pick_free_port(), stages_file)
    server.start()
    try:
        health = server.wait_healthy()
        worker_pid = server.worker_pid()
        results = asyncio.run(
            _run_steps(targets, viewers, seconds, server.port, worker_pid, connect_concurrency)
        )
    finally:
        server.stop()
    machine = (
        f"{platform.system()} {platform.machine()}, {os.cpu_count() or 1} CPUs, "
        f"Python {platform.python_version()}"
    )
    return Report(
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        machine=machine,
        engine=str(health.get("engine", "fake")),
        stage_ids=[stage for stage, _ in targets],
        seconds=seconds,
        steps=results,
        honesty=(
            "Fake engine (`ENGINE=fake`, no Gemini call): the server replayed the bundled "
            "samples as scripted captions, so the load is the WebSocket fan-out only. The "
            f"viewers ran in one client process on the same host as the server ({machine}) "
            "and shared its CPU; the network was the loopback interface (no Wi-Fi, TLS or "
            "reverse proxy). The spread therefore includes the client's own scheduling of "
            "all its sockets in one event loop and is an upper bound for what one server "
            "instance adds."
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    out_md = Path(args.out)
    report = run_loadtest(
        viewers=args.viewers,
        seconds=args.seconds,
        stages=args.stages,
        stages_file=Path(args.stages_file),
        port=args.port,
        connect_concurrency=args.connect_concurrency,
    )
    write_report(report, out_md, out_md.with_suffix(".json"))
    if args.scale_report:
        update_scale_report(report, Path(args.scale_report), out_md)
    print(render_markdown(report))
    print(f"written: {out_md} and {out_md.with_suffix('.json')}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
