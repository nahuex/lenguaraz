# SPDX-License-Identifier: Apache-2.0
"""License gate (Constitution Art. XVII.B): inventory every Python and frontend dependency,
fail on any license outside the allowlist and generate THIRD_PARTY_LICENSES.md.

Usage: uv run python scripts/license_check.py [--write] [--python-json F] [--npm-json F]
The JSON inputs are the outputs of ``pip-licenses --format=json --from=mixed`` and
``license-checker --production --json``; when omitted the tools are run.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "THIRD_PARTY_LICENSES.md"
WEB_DIR = ROOT / "web"

# Constitution Art. XVII.B.1 — allowed, Apache-2.0-compatible licenses (SPDX ids).
ALLOWED = {
    "Apache-2.0",
    "MIT",
    "MIT-0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "0BSD",
    "Zlib",
    "PSF-2.0",
    "Python-2.0",
    "MPL-2.0",
    "OFL-1.1",
    "Unlicense",
}
# Art. XVII.B.2 — never allowed. LGPL needs explicit human approval (listed in EXCEPTIONS).
FORBIDDEN_MARKERS = ("GPL", "AGPL", "SSPL", "BUSL", "COMMONS-CLAUSE", "ELASTIC", "NON-COMMERCIAL")
# Packages the owner approved by hand, with the reason (empty today).
EXCEPTIONS: dict[str, str] = {}

# Free-text license strings from classifiers/metadata → SPDX id.
NORMALIZE = {
    "MIT LICENSE": "MIT",
    "THE MIT LICENSE": "MIT",
    "APACHE SOFTWARE LICENSE": "Apache-2.0",
    "APACHE LICENSE 2.0": "Apache-2.0",
    "APACHE LICENSE, VERSION 2.0": "Apache-2.0",
    "APACHE 2.0": "Apache-2.0",
    "BSD LICENSE": "BSD-3-Clause",
    "BSD": "BSD-3-Clause",
    "NEW BSD": "BSD-3-Clause",
    "MOZILLA PUBLIC LICENSE 2.0 (MPL 2.0)": "MPL-2.0",
    "MOZILLA PUBLIC LICENSE 2.0": "MPL-2.0",
    "PYTHON SOFTWARE FOUNDATION LICENSE": "PSF-2.0",
    "ISC LICENSE (ISCL)": "ISC",
    "ISC LICENSE": "ISC",
    "THE UNLICENSE (UNLICENSE)": "Unlicense",
    "ZLIB/LIBPNG LICENSE": "Zlib",
}


@dataclass(frozen=True)
class Package:
    ecosystem: str
    name: str
    version: str
    license: str  # raw string as reported


@dataclass(frozen=True)
class Verdict:
    package: Package
    licenses: tuple[str, ...]  # normalized ids
    allowed: bool
    reason: str


def _unwrap(raw: str) -> str:
    text = raw.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    return text


def normalize(raw: str) -> str:
    text = _unwrap(raw)
    key = re.sub(r"\s+", " ", text).upper()
    return NORMALIZE.get(key, text)


def split_licenses(raw: str) -> list[str]:
    """'Apache-2.0 OR BSD-3-Clause', 'MIT; BSD' and '(MIT AND ISC)' → parts."""
    text = _unwrap(raw)
    parts = re.split(r"\s+OR\s+|\s*;\s*|\s+AND\s+", text, flags=re.IGNORECASE)
    return [normalize(p) for p in parts if p.strip()]


def classify(package: Package) -> Verdict:
    if package.name in EXCEPTIONS:
        return Verdict(package, (package.license,), True, f"exception: {EXCEPTIONS[package.name]}")
    parts = split_licenses(package.license)
    if not parts or package.license.upper() in {"UNKNOWN", "UNLICENSED", ""}:
        return Verdict(package, tuple(parts), False, "no license declared")
    upper = package.license.upper()
    disjunctive = bool(re.search(r"\s+OR\s+", package.license, flags=re.IGNORECASE))
    if disjunctive:
        # We may choose any option: allowed if at least one option is allowed.
        ok = any(p in ALLOWED for p in parts)
        return Verdict(
            package, tuple(parts), ok, "one option allowed" if ok else "no allowed option"
        )
    for marker in FORBIDDEN_MARKERS:
        if marker in upper and not any(p in ALLOWED for p in parts):
            return Verdict(package, tuple(parts), False, f"forbidden ({marker})")
    if all(p in ALLOWED for p in parts):
        return Verdict(package, tuple(parts), True, "allowed")
    unknown = [p for p in parts if p not in ALLOWED]
    return Verdict(package, tuple(parts), False, f"not in allowlist: {', '.join(unknown)}")


def parse_pip_licenses(payload: str) -> list[Package]:
    return [
        Package("python", p["Name"], p["Version"], p.get("License", "UNKNOWN"))
        for p in json.loads(payload)
    ]


def parse_license_checker(payload: str, own_name: str | None = None) -> list[Package]:
    packages: list[Package] = []
    for key, info in json.loads(payload).items():
        name, _, version = key.rpartition("@")
        if own_name and name == own_name:
            continue  # the project itself
        raw = info.get("licenses", "UNKNOWN")
        packages.append(
            Package("npm", name, version, ", ".join(raw) if isinstance(raw, list) else str(raw))
        )
    return packages


def run_tools() -> tuple[str, str]:
    pip = subprocess.run(
        ["uv", "run", "pip-licenses", "--format=json", "--from=mixed"],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    ).stdout
    npx = "npx.cmd" if sys.platform == "win32" else "npx"
    npm = subprocess.run(
        [npx, "license-checker", "--production", "--json"],
        check=True,
        capture_output=True,
        text=True,
        cwd=WEB_DIR,
    ).stdout
    return pip, npm


def own_package_name() -> str | None:
    try:
        return json.loads((WEB_DIR / "package.json").read_text(encoding="utf-8")).get("name")
    except (OSError, ValueError):
        return None


def render(verdicts: list[Verdict], stamp: str) -> str:
    lines = [
        "# Third-party licenses",
        "",
        "Generated by `make license-check` (`scripts/license_check.py`) — do not edit by hand.",
        f"Generated: {stamp}. Allowlist: Constitution Art. XVII.B.1 "
        f"({', '.join(sorted(ALLOWED))}).",
        "",
    ]
    for ecosystem, title in (
        ("python", "Python (runtime and dev, `uv`)"),
        ("npm", "Frontend (production, `npm`)"),
    ):
        rows = sorted(
            (v for v in verdicts if v.package.ecosystem == ecosystem),
            key=lambda v: v.package.name.lower(),
        )
        lines += [
            f"## {title}",
            "",
            "| Package | Version | License | Status |",
            "|---|---|---|---|",
        ]
        for v in rows:
            status = "ok" if v.allowed else f"**FAIL** — {v.reason}"
            lines.append(
                f"| {v.package.name} | {v.package.version} | {v.package.license} | {status} |"
            )
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="license_check")
    parser.add_argument("--write", action="store_true", help="write THIRD_PARTY_LICENSES.md")
    parser.add_argument("--python-json", type=Path, default=None)
    parser.add_argument("--npm-json", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.python_json and args.npm_json:
        pip_payload = args.python_json.read_text(encoding="utf-8")
        npm_payload = args.npm_json.read_text(encoding="utf-8")
    else:
        pip_payload, npm_payload = run_tools()
    packages = parse_pip_licenses(pip_payload) + parse_license_checker(
        npm_payload, own_package_name()
    )
    verdicts = [classify(p) for p in packages]
    failures = [v for v in verdicts if not v.allowed]
    for v in verdicts:
        flag = "ok  " if v.allowed else "FAIL"
        pkg = v.package
        print(f"{flag} {pkg.ecosystem:6} {pkg.name:32} {pkg.version:12} {pkg.license}")
    if args.write:
        OUTPUT.write_text(
            render(verdicts, datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%MZ")), encoding="utf-8"
        )
        print(f"wrote {OUTPUT.relative_to(ROOT)}")
    print(f"license-check: {len(verdicts)} packages, {len(failures)} violation(s)")
    for v in failures:
        pkg = v.package
        print(f"  {pkg.ecosystem} {pkg.name}=={pkg.version}: {pkg.license} -> {v.reason}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
