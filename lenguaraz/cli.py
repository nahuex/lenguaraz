# SPDX-License-Identifier: Apache-2.0
"""``lenguaraz`` command line: serve, samples, smoke-stt, mvp-check."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from lenguaraz import __version__
from lenguaraz.config import ConfigError, load_settings
from lenguaraz.logsetup import configure_logging


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
        if command == "mvp-check":
            from lenguaraz.tools.mvp_check import main as mvp_main

            return mvp_main(extra)
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    parser.print_help()
    return 1


def _serve(args: argparse.Namespace) -> int:
    import uvicorn

    settings = load_settings()
    configure_logging(settings.log_level)
    host = args.host or settings.host
    port = args.port or settings.port
    if args.reload:
        uvicorn.run(
            "lenguaraz.api.app:build",
            factory=True,
            host=host,
            port=port,
            reload=True,
            reload_dirs=["lenguaraz"],
            log_config=None,
        )
        return 0
    from lenguaraz.api.app import create_app

    uvicorn.run(create_app(settings), host=host, port=port, log_config=None)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
