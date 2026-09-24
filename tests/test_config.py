# SPDX-License-Identifier: Apache-2.0
"""Spec 001 — FR-001-01, AC-1 (config side), AC-2."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from lenguaraz.config import (
    ConfigError,
    EngineKind,
    Settings,
    StageConfig,
    StagesFile,
    SttMode,
    load_settings,
    short_code,
)

TWO_STAGES = """
stages:
  - id: main
    name: "Main Stage"
    source: "samples/en_placeholder.wav"
    source_lang: ["en-US"]
    targets: ["es", "pt"]
    talk: { title: "Observability with eBPF", abstract: "Kernel-level tracing." }
    glossary: ["eBPF", "Kubernetes", " eBPF ", ""]
  - id: workshop-1
    name: "Workshop"
    source: "srt://10.0.0.5:9000?mode=caller"
    source_lang: []
    targets: ["en"]
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "stages.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_stages_file_valid(tmp_path: Path) -> None:
    stages = StagesFile.load(write(tmp_path, TWO_STAGES))
    assert [s.id for s in stages.stages] == ["main", "workshop-1"]
    main = stages.by_id("main")
    assert main is not None
    assert main.primary_source_lang == "en"
    assert main.languages() == ["en", "es", "pt"]
    assert main.glossary == ["eBPF", "Kubernetes"]  # stripped, deduplicated, empties dropped
    workshop = stages.by_id("workshop-1")
    assert workshop is not None
    assert workshop.primary_source_lang is None  # auto-detect
    assert workshop.languages() == ["en"]
    assert stages.by_id("nope") is None


@pytest.mark.parametrize(
    ("yaml_text", "needle"),
    [
        (TWO_STAGES.replace("workshop-1", "main"), "duplicate stage id 'main'"),
        (TWO_STAGES.replace('source: "samples/en_placeholder.wav"', 'source: "  "'), "source"),
        (TWO_STAGES.replace('["en-US"]', '["es_ES"]'), "source_lang"),
        (TWO_STAGES.replace('["es", "pt"]', '["es-419"]'), "targets"),
        (TWO_STAGES.replace("id: main", "id: Main Stage"), "stage id"),
        ("stages: []", "stages"),
        ("- not a mapping", "expected a mapping"),
        ("stages: [ { id: x, name: X, source: f.wav, unknown: 1 } ]", "unknown"),
    ],
)
def test_invalid_config_names_the_field(tmp_path: Path, yaml_text: str, needle: str) -> None:
    with pytest.raises(ConfigError) as info:
        StagesFile.load(write(tmp_path, yaml_text))
    assert needle in str(info.value)


def test_missing_file_is_a_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        StagesFile.load(tmp_path / "absent.yaml")


def test_invalid_yaml_is_a_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="invalid YAML"):
        StagesFile.load(write(tmp_path, "stages: [unclosed"))


def test_glossary_is_capped_at_100_terms() -> None:
    with pytest.raises(ValidationError, match="maximum is 100"):
        StageConfig(id="a", name="A", source="x.wav", glossary=[f"term{i}" for i in range(101)])
    with pytest.raises(ValidationError, match="exceeds 64"):
        StageConfig(id="a", name="A", source="x.wav", glossary=["x" * 65])


def test_short_code() -> None:
    assert short_code("en-US") == "en"
    assert short_code("es-419") == "es"
    assert short_code("pt") == "pt"
    assert short_code("cmn-Hans-CN") == "cmn"


def test_settings_fake_engine_needs_no_key() -> None:
    settings = Settings(_env_file=None, engine="fake")
    assert settings.engine is EngineKind.FAKE
    assert settings.dry_run is True
    assert settings.stt_mode is SttMode.SMART
    assert settings.session_rotate_seconds == 540
    assert settings.gemini_stt_model == "gemini-3.5-transcribe-live"
    assert settings.gemini_tts_model == "gemini-3.8-flash-lite-tts"


def test_settings_gemini_requires_key() -> None:
    with pytest.raises(ValidationError, match="GEMINI_API_KEY is required"):
        Settings(_env_file=None, engine="gemini")
    with pytest.raises(ValidationError, match="GEMINI_API_KEY is required"):
        Settings(_env_file=None, engine="gemini", gemini_api_key="   ")
    with pytest.raises(ConfigError, match="GEMINI_API_KEY is required"):
        load_settings(_env_file=None, engine="gemini")


def test_settings_secret_never_leaks_in_repr() -> None:
    settings = Settings(_env_file=None, engine="gemini", gemini_api_key="AIza-very-secret")
    assert "very-secret" not in repr(settings)
    assert "very-secret" not in str(settings)
    assert settings.api_key() == "AIza-very-secret"


def test_settings_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENGINE", "fake")
    monkeypatch.setenv("STT_MODE", "VERBATIM")
    monkeypatch.setenv("SESSION_ROTATE_SECONDS", "120")
    monkeypatch.setenv("PORT", "9000")
    settings = Settings(_env_file=None)
    assert settings.stt_mode is SttMode.VERBATIM
    assert settings.session_rotate_seconds == 120
    assert settings.port == 9000


def test_settings_rejects_out_of_range_rotation() -> None:
    with pytest.raises(ValidationError, match="session_rotate_seconds"):
        Settings(_env_file=None, engine="fake", session_rotate_seconds=5)
