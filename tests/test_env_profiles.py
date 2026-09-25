# SPDX-License-Identifier: Apache-2.0
"""The shipped ``examples/env/*.env`` profiles parse to what their comments promise.

Constitution Art. XVII.D.4 (docs are code): ``make docs-check`` only proves the profile files
exist, so their contents are checked here. Regression: an inline ``# comment`` after an EMPTY
value used to become the value in the developer path (``ADMIN_TOKEN='# openssl rand -hex 32'``,
``ALWAYS_ON_LANGS='# e.g. es …'``), while Docker Compose dropped it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from lenguaraz.config import EngineKind, Settings

PROFILE_DIR = Path(__file__).resolve().parent.parent / "examples" / "env"
PROFILES = sorted(PROFILE_DIR.glob("*.env"))


@pytest.fixture(autouse=True)
def _only_the_profile_feeds_the_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """The shell's own ``ENGINE=fake`` and friends must not leak into the parsed profile."""
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


def _load(profile: Path) -> Settings:
    # The gemini profiles ship an empty key on purpose; a placeholder satisfies the validator.
    return Settings(_env_file=profile, gemini_api_key=SecretStr("placeholder-for-the-test"))


def test_the_three_documented_profiles_ship() -> None:
    assert {p.name for p in PROFILES} >= {"dry-run.env", "production.env", "free-tier.env"}


@pytest.mark.parametrize("profile", PROFILES, ids=[p.name for p in PROFILES])
def test_no_inline_comment_leaks_into_a_value(profile: Path) -> None:
    settings = _load(profile)
    for name in Settings.model_fields:
        value = getattr(settings, name)
        text = value.get_secret_value() if isinstance(value, SecretStr) else value
        assert "#" not in str(text), f"{profile.name}: {name.upper()} parsed as {text!r}"


def test_free_tier_profile_stays_within_fifteen_requests_per_minute() -> None:
    settings = _load(PROFILE_DIR / "free-tier.env")
    assert settings.engine is EngineKind.GEMINI
    assert settings.progressive_translation is False
    assert settings.always_on_langs == ""
    assert settings.auto_glossary is False
    assert settings.translate_context_segments == 1


def test_production_profile_keeps_progressive_translation_and_auto_glossary() -> None:
    settings = _load(PROFILE_DIR / "production.env")
    assert settings.engine is EngineKind.GEMINI
    assert settings.progressive_translation is True
    assert settings.auto_glossary is True
    assert settings.always_on_langs == ""
    assert settings.ws_max_conn_per_ip == 200
