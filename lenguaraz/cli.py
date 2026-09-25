# SPDX-License-Identifier: Apache-2.0
"""``lenguaraz`` command line: serve, samples, smoke-*, simulate, loadtest, mvp-check."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from typing import Any

from lenguaraz import __version__
from lenguaraz.config import ConfigError, Settings, load_settings
from lenguaraz.logsetup import configure_logging

log = logging.getLogger("lenguaraz.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lenguaraz", description="Lenguaraz — live captions")
    parser.add_argument("--version", action="version", version=f"lenguaraz {__version__}")
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="run the API and the audience view")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    serve.add_argument("--reload", action="store_true", help="auto-reload on code changes")

    for name, help_text in (
        ("samples", "generate test audio with Gemini TTS (uses quota)"),
        ("smoke-stt", "transcribe a sample with the real engine (uses quota)"),
        ("smoke-translate", "translate sample segments with the real model (uses quota)"),
        ("mvp-check", "scripted check of the MVP gates"),
        ("simulate", "run N stages in one process and write the scale report"),
        ("loadtest", "viewer fan-out load test against a fake-engine server (no quota)"),
    ):
        sub.add_parser(name, help=help_text, add_help=False)  # tool parses its own options
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args, extra = parser.parse_known_args(argv)
    command = args.command or "serve"
    try:
        if command == "serve":
            return _serve(args)
        if command == "samples":
            from lenguaraz.tools.samples import main as samples_main

            return samples_main(extra)
        if command == "smoke-stt":
            from lenguaraz.tools.smoke_stt import main as smoke_main

            return smoke_main(extra)
        if command == "smoke-translate":
            from lenguaraz.tools.smoke_translate import main as smoke_translate_main

            return smoke_translate_main(extra)
        if command == "simulate":
            from lenguaraz.tools.simulate import main as simulate_main

            return simulate_main(extra)
        if command == "loadtest":
            from lenguaraz.tools.loadtest import main as loadtest_main

            return loadtest_main(extra)
        if command == "mvp-check":
            from lenguaraz.tools.mvp_check import main as mvp_main

            return mvp_main(extra)
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    parser.print_help()
    return 1


def build_uvicorn_kwargs(
    settings: Settings, *, host: str, port: int, reload: bool = False
) -> dict[str, Any]:
    """Keyword arguments for ``uvicorn.run`` / ``uvicorn.Config`` derived from the settings.

    Pure function (unit-tested, spec 013): TLS files become ``ssl_*`` arguments when
    ``settings.tls_enabled``; proxy trust is always passed so the per-IP limiter and the logs
    see the real client address behind a trusted proxy (FR-013-02).
    """
    kwargs: dict[str, Any] = {
        "host": host,
        "port": port,
        "log_config": None,
        "proxy_headers": settings.proxy_headers,
        "forwarded_allow_ips": settings.forwarded_allow_ips,
    }
    if reload:
        kwargs["reload"] = True
        kwargs["reload_dirs"] = ["lenguaraz"]
    if settings.tls_enabled:
        kwargs["ssl_certfile"] = str(settings.tls_cert_file)
        kwargs["ssl_keyfile"] = str(settings.tls_key_file)
        if settings.tls_ca_file is not None:
            kwargs["ssl_ca_certs"] = str(settings.tls_ca_file)
    return kwargs


def _serve(args: argparse.Namespace) -> int:
    import uvicorn

    settings = load_settings()
    configure_logging(settings.log_level)
    host = args.host or settings.host
    port = args.port or settings.port
    kwargs = build_uvicorn_kwargs(settings, host=host, port=port, reload=args.reload)
    scheme = "https" if settings.tls_enabled else "http"
    log.info(
        "serving on %s://%s:%d (captions over %s; proxy headers %s from %s)",
        scheme,
        host,
        port,
        "wss" if settings.tls_enabled else "ws",
        "trusted" if settings.proxy_headers else "ignored",
        settings.forwarded_allow_ips,
    )
    if args.reload:
        uvicorn.run("lenguaraz.api.app:build", factory=True, **kwargs)
        return 0
    from lenguaraz.api.app import create_app

    uvicorn.run(create_app(settings), **kwargs)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
