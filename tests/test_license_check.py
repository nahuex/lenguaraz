# SPDX-License-Identifier: Apache-2.0
"""Spec 007 AC-1: the license gate classifies against the constitution allowlist."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "license_check.py"
spec = importlib.util.spec_from_file_location("license_check", SCRIPT)
assert spec and spec.loader
license_check = importlib.util.module_from_spec(spec)
sys.modules["license_check"] = license_check
spec.loader.exec_module(license_check)

Package = license_check.Package


@pytest.mark.parametrize(
    ("raw", "allowed", "reason_part"),
    [
        ("MIT", True, "allowed"),
        ("MIT License", True, "allowed"),
        ("Apache Software License", True, "allowed"),
        ("BSD License", True, "allowed"),
        ("Mozilla Public License 2.0 (MPL 2.0)", True, "allowed"),
        ("Apache-2.0 OR BSD-3-Clause", True, "one option"),
        ("Apache Software License; MIT License", True, "allowed"),
        ("(MIT AND ISC)", True, "allowed"),
        ("GPL-3.0-only", False, "forbidden"),
        ("AGPL-3.0", False, "forbidden"),
        ("LGPL-2.1", False, "forbidden"),
        ("SSPL-1.0", False, "forbidden"),
        ("UNKNOWN", False, "no license"),
        ("UNLICENSED", False, "no license"),
        ("Proprietary", False, "not in allowlist"),
        ("GPL-2.0 OR MIT", True, "one option"),
    ],
)
def test_classify(raw: str, allowed: bool, reason_part: str) -> None:
    verdict = license_check.classify(Package("python", "pkg", "1.0", raw))
    assert verdict.allowed is allowed, verdict
    assert reason_part in verdict.reason


def test_parsers_skip_own_package_and_handle_lists() -> None:
    pip = json.dumps([{"Name": "fastapi", "Version": "0.141.0", "License": "MIT License"}])
    npm = json.dumps(
        {
            "lenguaraz-web@0.1.0": {"licenses": "UNLICENSED"},
            "react@19.3.0": {"licenses": "MIT"},
            "dual@1.0.0": {"licenses": ["MIT", "ISC"]},
        }
    )
    packages = license_check.parse_pip_licenses(pip) + license_check.parse_license_checker(
        npm, "lenguaraz-web"
    )
    names = [(p.ecosystem, p.name, p.license) for p in packages]
    assert names == [
        ("python", "fastapi", "MIT License"),
        ("npm", "react", "MIT"),
        ("npm", "dual", "MIT, ISC"),
    ]


def test_main_writes_report_and_fails_on_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    py = tmp_path / "py.json"
    npm = tmp_path / "npm.json"
    py.write_text(json.dumps([{"Name": "ok", "Version": "1", "License": "MIT"}]), encoding="utf-8")
    npm.write_text(json.dumps({"react@1": {"licenses": "MIT"}}), encoding="utf-8")
    out = tmp_path / "THIRD_PARTY_LICENSES.md"
    monkeypatch.setattr(license_check, "OUTPUT", out)
    monkeypatch.setattr(license_check, "ROOT", tmp_path)
    assert license_check.main(["--write", "--python-json", str(py), "--npm-json", str(npm)]) == 0
    text = out.read_text(encoding="utf-8")
    assert (
        "do not edit by hand" in text
        and "| ok | 1 | MIT | ok |" in text
        and "| react | 1 | MIT | ok |" in text
    )

    py.write_text(
        json.dumps([{"Name": "bad", "Version": "2", "License": "GPL-3.0"}]), encoding="utf-8"
    )
    assert license_check.main(["--python-json", str(py), "--npm-json", str(npm)]) == 1
