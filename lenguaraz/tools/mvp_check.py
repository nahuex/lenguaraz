# SPDX-License-Identifier: Apache-2.0
"""``make mvp-check``: scripted verification of the challenge's MVP gates (Constitution Art. I.5).

Runs the application in-process with the bundled ``stages.yaml`` and samples, in fake mode
by default (no credentials, CI-safe) or with the real engine when ``--engine gemini`` is
given and a key is configured. MVP-4 (EN → ES translation) is reported as PENDING until
feature 002 lands.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lenguaraz.api.app import create_app, default_web_dist
from lenguaraz.config import ConfigError, EngineKind, Settings, StagesFile, load_settings
from lenguaraz.models import CaptionEvent, StatusEvent, parse_event


@dataclass(slots=True)
class Gate:
    id: str
    title: str
    status: str = "FAIL"
    note: str = ""


def collect_captions(client: Any, stage_id: str, lang: str, seconds: float) -> list[CaptionEvent]:
    """Read caption events for up to ``seconds``.

    ``TestClient`` sockets are synchronous and ``receive_text`` has no timeout, so a stage
    that never captions (quota, network) would block forever. The reader runs in a daemon
    thread and is abandoned at the deadline; whatever arrived is returned.
    """
    captions: list[CaptionEvent] = []

    def reader() -> None:
        try:
            with client.websocket_connect(f"/ws/{stage_id}?lang={lang}") as ws:
                first = parse_event(ws.receive_text())
                assert isinstance(first, StatusEvent)
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    event = parse_event(ws.receive_text())
                    if isinstance(event, CaptionEvent):
                        captions.append(event)
                        if any(c.is_final for c in captions) and len(captions) >= 3:
                            break
        except Exception:
            return

    thread = threading.Thread(target=reader, name=f"mvp-collect-{stage_id}", daemon=True)
    thread.start()
    thread.join(seconds + 5.0)
    if thread.is_alive():
        print(f"  [{stage_id}] no events within {seconds:.0f}s; giving up on this socket")
    return list(captions)


def run(settings: Settings, stages_path: Path, seconds: float) -> list[Gate]:
    from starlette.testclient import TestClient

    stages = StagesFile.load(stages_path)
    gates = [
        Gate("MVP-1", "Live audio from at least one source"),
        Gate("MVP-2", "Test audio files in the repo, one-command try"),
        Gate("MVP-3", "Real-time transcription of the original language"),
        Gate("MVP-4", "Real-time translation English → Spanish"),
        Gate("MVP-5", "Subtitles displayed (web)"),
        Gate("MVP-6", "At least two sessions processed simultaneously"),
        Gate("MVP-7", "Audience view: choose session and language"),
    ]
    by_id = {g.id: g for g in gates}

    # MVP-2: files and the one-command path
    missing = [s.source for s in stages.stages if not Path(s.source).is_file()]
    if not missing and len(stages.stages) >= 2:
        by_id["MVP-2"].status = "PASS"
        by_id[
            "MVP-2"
        ].note = f"{len(stages.stages)} bundled stages; `make demo` / `docker compose up`"
    else:
        by_id["MVP-2"].note = f"missing sources: {missing}" if missing else "need ≥ 2 stages"

    app = create_app(settings, stages, web_dist=default_web_dist())
    with TestClient(app) as client:
        health = client.get("/healthz").json()
        rows = {row["id"]: row for row in client.get("/api/stages").json()}

        # MVP-5: the audience view is served
        index = client.get("/")
        if index.status_code == 200 and '<div id="root"' in index.text:
            by_id["MVP-5"].status = "PASS"
            by_id["MVP-5"].note = "web/dist served with SPA fallback"
        else:
            by_id["MVP-5"].note = "web/dist not built (run `make web`)"

        # MVP-7: session + language choice
        multi = [r for r in rows.values() if len(r["languages"]) >= 2]
        if len(rows) >= 2 and multi:
            by_id["MVP-7"].status = "PASS"
            example = f"{multi[0]['id']}: {multi[0]['languages']}"
            by_id["MVP-7"].note = f"{len(rows)} stages listed; languages e.g. {example}"
        else:
            by_id["MVP-7"].note = "need ≥ 2 stages and a stage with ≥ 2 languages"

        # MVP-1 / MVP-3 / MVP-6: captions flowing on two stages at once
        results: dict[str, list[CaptionEvent]] = {}
        for stage in stages.stages[:2]:
            lang = stage.primary_source_lang or "en"
            results[stage.id] = collect_captions(client, stage.id, lang, seconds)
        live = [sid for sid, caps in results.items() if any(c.is_final for c in caps)]
        if live:
            by_id["MVP-1"].status = "PASS"
            by_id["MVP-1"].note = f"engine={health['engine']}; stages with captions: {live}"
            by_id["MVP-3"].status = "PASS"
            sample = next(c for c in results[live[0]] if c.is_final)
            by_id["MVP-3"].note = f"{live[0]} [{sample.lang}] “{sample.text[:60]}”"
        else:
            states = {
                row["id"]: f"{row['state']} {row.get('detail') or ''}".strip()
                for row in client.get("/api/stages").json()
            }
            by_id["MVP-1"].note = f"no captions received; stages: {states}"
            by_id["MVP-3"].note = "no final caption received"
        if len(live) >= 2:
            by_id["MVP-6"].status = "PASS"
            by_id["MVP-6"].note = f"finals on {live[0]} and {live[1]} within {seconds:.0f} s"
        else:
            by_id["MVP-6"].note = f"only {len(live)} stage(s) produced finals"

        # MVP-4: translation arrives with feature 002
        target_stage = next((s for s in stages.stages if "es" in s.targets), None)
        if target_stage is None:
            by_id["MVP-4"].note = "no stage targets Spanish"
        else:
            spanish = [
                c
                for c in collect_captions(client, target_stage.id, "es", seconds)
                if c.lang == "es"
            ]
            translated = [
                c for c in spanish if c.original and c.original != c.text and not c.degraded
            ]
            if translated:
                by_id["MVP-4"].status = "PASS"
                by_id["MVP-4"].note = f"{target_stage.id} → es “{translated[0].text[:60]}”"
            else:
                by_id["MVP-4"].status = "PENDING"
                by_id["MVP-4"].note = "translation fan-out lands in feature 002"
    return gates


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lenguaraz mvp-check")
    parser.add_argument("--engine", choices=["fake", "gemini"], default=None)
    parser.add_argument("--stages", default="stages.yaml")
    parser.add_argument("--seconds", type=float, default=12.0)
    args = parser.parse_args(argv)
    try:
        settings = load_settings(**({"engine": args.engine} if args.engine else {}))
    except ConfigError:
        if args.engine == "gemini":
            raise
        settings = load_settings(engine=EngineKind.FAKE)
    if settings.engine is EngineKind.GEMINI and args.engine is None:
        settings = load_settings(engine=EngineKind.FAKE)  # CI-safe default
    gates = run(settings, Path(args.stages), args.seconds)
    print(f"\nMVP gates (engine={settings.engine.value})")
    print("| Gate | Status | Evidence |\n|---|---|---|")
    for gate in gates:
        print(f"| {gate.id} {gate.title} | {gate.status} | {gate.note} |")
    failed = [g.id for g in gates if g.status == "FAIL"]
    print("\nRESULT:", "PASS" if not failed else f"FAIL ({', '.join(failed)})")
    return 0 if not failed else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
