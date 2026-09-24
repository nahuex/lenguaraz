# SPDX-License-Identifier: Apache-2.0
"""Configuration: environment settings and the stages file.

Everything event-specific (stages, languages, glossaries) lives in ``stages.yaml``;
everything deployment-specific (engine, models, ports, secrets) lives in the
environment. Both are validated with pydantic and fail fast with a readable message
(Constitution Art. VIII.3, Art. XI.1).
"""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = [
    "ConfigError",
    "EngineKind",
    "Settings",
    "StageConfig",
    "StagesFile",
    "SttMode",
    "TalkInfo",
    "VadMode",
    "short_code",
]

MAX_GLOSSARY_TERMS = 100
MAX_GLOSSARY_TERM_CHARS = 64

_STAGE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
_BCP47 = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
_SHORT_CODE = re.compile(r"^[a-z]{2,3}$")


class ConfigError(Exception):
    """Raised when configuration cannot be loaded or is invalid."""


class EngineKind(StrEnum):
    GEMINI = "gemini"
    FAKE = "fake"


class SttMode(StrEnum):
    VERBATIM = "VERBATIM"
    SMART = "SMART"


class VadMode(StrEnum):
    SERVER = "server"  # rely on the server's automatic VAD only
    HYBRID = "hybrid"  # client-side silence detection sends audio_stream_end (fast finalization)


def short_code(language: str) -> str:
    """Return the primary subtag of a BCP-47 tag (``en-US`` → ``en``)."""
    return language.split("-", 1)[0].lower()


class TalkInfo(BaseModel):
    """Talk metadata. Untrusted data when placed in prompts (Art. VIII.4)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="", max_length=200)
    abstract: str = Field(default="", max_length=2000)


class StageConfig(BaseModel):
    """One stage: where the audio comes from and which languages it needs."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str = Field(min_length=1, max_length=80)
    source: str
    source_lang: list[str] = Field(default_factory=list)
    targets: list[str] = Field(default_factory=list)
    talk: TalkInfo = Field(default_factory=TalkInfo)
    glossary: list[str] = Field(default_factory=list)
    loop: bool = False  # replay a file source forever (demo stages)

    @field_validator("id")
    @classmethod
    def _valid_id(cls, value: str) -> str:
        if not _STAGE_ID.match(value):
            raise ValueError(
                f"stage id {value!r} must be lowercase letters, digits or '-' (max 32 chars)"
            )
        return value

    @field_validator("source")
    @classmethod
    def _non_empty_source(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("source must be a file path, URL or device (it is empty)")
        return value

    @field_validator("source_lang")
    @classmethod
    def _valid_source_lang(cls, value: list[str]) -> list[str]:
        for tag in value:
            if not _BCP47.match(tag):
                raise ValueError(f"source_lang entry {tag!r} is not a BCP-47 tag like 'en-US'")
        return value

    @field_validator("targets")
    @classmethod
    def _valid_targets(cls, value: list[str]) -> list[str]:
        seen: list[str] = []
        for code in value:
            if not _SHORT_CODE.match(code):
                raise ValueError(f"targets entry {code!r} must be a short code like 'es' or 'pt'")
            if code not in seen:
                seen.append(code)
        return seen

    @field_validator("glossary")
    @classmethod
    def _valid_glossary(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for term in value:
            term = term.strip()
            if not term:
                continue
            if len(term) > MAX_GLOSSARY_TERM_CHARS:
                raise ValueError(
                    f"glossary term {term[:20]!r}… exceeds {MAX_GLOSSARY_TERM_CHARS} characters"
                )
            if term not in cleaned:
                cleaned.append(term)
        if len(cleaned) > MAX_GLOSSARY_TERMS:
            raise ValueError(
                f"glossary has {len(cleaned)} terms; the maximum is {MAX_GLOSSARY_TERMS}"
            )
        return cleaned

    @property
    def primary_source_lang(self) -> str | None:
        """Short code of the first configured source language, or None for auto-detect."""
        return short_code(self.source_lang[0]) if self.source_lang else None

    def languages(self) -> list[str]:
        """Short codes an audience member can pick: source languages first, then targets."""
        codes: list[str] = []
        for tag in self.source_lang:
            code = short_code(tag)
            if code not in codes:
                codes.append(code)
        for code in self.targets:
            if code not in codes:
                codes.append(code)
        return codes


class StagesFile(BaseModel):
    """The ``stages.yaml`` document."""

    model_config = ConfigDict(extra="forbid")

    stages: list[StageConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> StagesFile:
        seen: set[str] = set()
        for stage in self.stages:
            if stage.id in seen:
                raise ValueError(f"duplicate stage id {stage.id!r}")
            seen.add(stage.id)
        return self

    def by_id(self, stage_id: str) -> StageConfig | None:
        return next((s for s in self.stages if s.id == stage_id), None)

    @classmethod
    def load(cls, path: Path | str) -> StagesFile:
        path = Path(path)
        if not path.is_file():
            raise ConfigError(f"stages file not found: {path}")
        try:
            raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ConfigError(f"{path}: invalid YAML: {exc}") from exc
        if not isinstance(raw, dict):
            raise ConfigError(f"{path}: expected a mapping with a 'stages' list at the top level")
        try:
            return cls.model_validate(raw)
        except ValidationError as exc:
            raise ConfigError(f"{path}: {format_validation_error(exc)}") from exc


def format_validation_error(exc: ValidationError) -> str:
    """Turn a pydantic error into one readable line per problem, naming the field."""
    lines = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"]) or "<root>"
        lines.append(f"{loc}: {err['msg']}")
    return "; ".join(lines)


class Settings(BaseSettings):
    """Deployment settings from the environment (and ``.env`` when present).

    Secrets are ``SecretStr`` so they never appear in logs or ``repr``.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    engine: EngineKind = EngineKind.GEMINI
    gemini_api_key: SecretStr | None = None
    admin_token: SecretStr = SecretStr("change-me-long-random")
    gemini_stt_model: str = "gemini-3.5-transcribe-live"
    gemini_translate_model: str = "gemini-3.5-flash-lite"
    gemini_interpreter_model: str = "gemini-3.5-live-translate-preview"
    gemini_tts_model: str = "gemini-3.8-flash-lite-tts"
    stt_mode: SttMode = SttMode.SMART
    vad_mode: VadMode = VadMode.HYBRID
    vad_silence_ms: int = Field(default=500, ge=100, le=5000)
    vad_threshold: int = Field(default=300, ge=1, le=20000)
    session_rotate_seconds: int = Field(default=540, ge=30, le=600)
    progressive_translation: bool = True
    always_on_langs: str = "es"  # comma-separated short codes translated even with no listener
    lang_grace_seconds: float = Field(default=10.0, ge=0, le=600)
    lang_reconcile_debounce_ms: int = Field(default=250, ge=0, le=5000)
    progressive_min_words: int = Field(default=6, ge=1, le=50)
    progressive_debounce_ms: int = Field(default=600, ge=100, le=5000)
    translate_max_output_tokens: int = Field(default=512, ge=16, le=8192)
    gemini_translate_thinking: str = Field(default="minimal", pattern="^(minimal|low|medium|high)$")
    translate_context_segments: int = Field(default=3, ge=0, le=10)
    gemini_translate_api: str = Field(
        default="generate_content", pattern="^(generate_content|interactions)$"
    )
    log_transcripts: bool = False
    redis_url: str = ""
    stages_file: Path = Path("stages.yaml")
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    ws_max_conn_per_ip: int = Field(default=50, ge=1)
    ffmpeg_bin: str = "ffmpeg"
    web_dist: Path | None = None  # built frontend; default: web/dist next to the package

    @model_validator(mode="after")
    def _key_required_for_gemini(self) -> Settings:
        if self.engine is EngineKind.GEMINI and not (
            self.gemini_api_key and self.gemini_api_key.get_secret_value().strip()
        ):
            raise ValueError(
                "GEMINI_API_KEY is required when ENGINE=gemini "
                "(set ENGINE=fake for a credential-free dry run)"
            )
        return self

    @property
    def dry_run(self) -> bool:
        return self.engine is EngineKind.FAKE

    def always_on(self) -> list[str]:
        """Short codes from ``ALWAYS_ON_LANGS`` (comma-separated), lower-cased, deduplicated."""
        codes: list[str] = []
        for raw in self.always_on_langs.split(","):
            code = raw.strip().lower()
            if code and code not in codes:
                codes.append(code)
        return codes

    def api_key(self) -> str:
        """The Gemini API key. Only the engine calls this; never log the result."""
        if self.gemini_api_key is None:
            raise ConfigError("GEMINI_API_KEY is not set")
        return self.gemini_api_key.get_secret_value()


def load_settings(**overrides: Any) -> Settings:
    """Build ``Settings`` with a readable error (used by the CLI)."""
    try:
        return Settings(**overrides)
    except ValidationError as exc:
        raise ConfigError(format_validation_error(exc)) from exc
