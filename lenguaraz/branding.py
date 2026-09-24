# SPDX-License-Identifier: Apache-2.0
"""Branding as runtime configuration (Constitution Art. XVII.C): event name, colors, logo.

No brand asset is ever committed; a logo is a URL or a file under ``branding/local/`` (git
ignored). Values are validated so a config file can never inject markup into the pages.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_TEXT = 120


class Branding(BaseModel):
    """What the audience pages show about the event. Defaults are the neutral Lenguaraz theme."""

    model_config = ConfigDict(extra="forbid")

    event_name: str = Field(default="Lenguaraz", max_length=MAX_TEXT)
    tagline: str = Field(default="Live captions and translation", max_length=MAX_TEXT)
    primary_color: str = "#2563eb"
    logo_url: str | None = None
    footer: str = Field(
        default="Powered by Lenguaraz · open source under Apache-2.0", max_length=MAX_TEXT
    )

    @field_validator("event_name", "tagline", "footer")
    @classmethod
    def _plain_text(cls, value: str) -> str:
        cleaned = value.replace("<", "‹").replace(">", "›").strip()  # noqa: RUF001
        return cleaned

    @field_validator("primary_color")
    @classmethod
    def _hex_color(cls, value: str) -> str:
        if not HEX_COLOR.match(value):
            raise ValueError("primary_color must be #RRGGBB")
        return value.lower()

    @field_validator("logo_url")
    @classmethod
    def _safe_logo(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip()
        if value.startswith(("https://", "http://", "/branding/")):
            return value
        raise ValueError("logo_url must be an http(s) URL or a path under /branding/")

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump()


def load_branding(path: Path | None) -> Branding:
    """Read ``branding.yaml``; a missing file means the defaults (never an error)."""
    if path is None or not path.is_file():
        return Branding()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: branding file must be a mapping")
    return Branding.model_validate(data)
