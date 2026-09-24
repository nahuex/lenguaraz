# SPDX-License-Identifier: Apache-2.0
"""Spec 008 AC-3: branding is validated runtime configuration with safe defaults."""

from __future__ import annotations

from pathlib import Path

import pytest

from lenguaraz.branding import Branding, load_branding


def test_defaults_without_a_file(tmp_path: Path) -> None:
    branding = load_branding(tmp_path / "missing.yaml")
    assert branding == Branding()
    assert branding.event_name == "Lenguaraz" and branding.logo_url is None
    assert load_branding(None) == Branding()


def test_file_values_are_validated(tmp_path: Path) -> None:
    path = tmp_path / "branding.yaml"
    path.write_text(
        "event_name: 'My <b>Conf</b>'\nprimary_color: '#7C3AED'\nlogo_url: /branding/logo.svg\n",
        encoding="utf-8",
    )
    branding = load_branding(path)
    assert branding.event_name == "My ‹b›Conf‹/b›"  # noqa: RUF001 — markup neutralized
    assert branding.primary_color == "#7c3aed"
    assert branding.logo_url == "/branding/logo.svg"
    assert branding.as_dict()["footer"].startswith("Powered by Lenguaraz")


@pytest.mark.parametrize(
    "content",
    [
        "primary_color: red\n",
        "primary_color: '#fff'\n",
        "logo_url: 'javascript:alert(1)'\n",
        "logo_url: ../secret.png\n",
        "unknown_field: 1\n",
        "- not a mapping\n",
    ],
)
def test_invalid_files_are_rejected(tmp_path: Path, content: str) -> None:
    path = tmp_path / "branding.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        load_branding(path)


def test_api_branding_serves_the_file_values(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from lenguaraz.api.app import create_app
    from lenguaraz.config import Settings, StagesFile
    from lenguaraz.stt.fake import FakeSttEngine

    path = tmp_path / "branding.yaml"
    path.write_text("event_name: Conf\nprimary_color: '#112233'\n", encoding="utf-8")
    stages = StagesFile.load(Path("examples/stages.minimal.yaml"))
    app = create_app(
        Settings(_env_file=None, engine="fake", branding_file=path),
        stages,
        engine=FakeSttEngine(),
        web_dist=tmp_path,
    )
    client = TestClient(app)  # no lifespan: stages are not started for this check
    payload = client.get("/api/branding").json()
    assert payload["event_name"] == "Conf" and payload["primary_color"] == "#112233"
    assert payload["logo_url"] is None and payload["tagline"] == "Live captions and translation"
