"""Runtime configuration loaded from an optional ``config.toml``.

Everything has a sensible default (see ``config.example.toml``), so the toolkit
runs with no config at all. A present file overrides only the keys it sets; the
rest fall back to the defaults below. Field-level note-type mapping lives
separately in ``mappings.toml`` (see ``scripts/adapter``).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_URL = "http://localhost:8765"

_DEFAULT_TARGETS = {
    "qa": "MONO Basic",
    "cloze": "MONO Cloze",
    "list": "MONO Overlapping",
}


class ConfigError(ValueError):
    """Raised when config.toml contains an invalid setting."""


@dataclass
class Config:
    """Resolved settings for an import run."""

    ankiconnect_url: str = DEFAULT_URL
    sync_after_import: bool = True
    default_deck: str = "Inbox"
    auto_tag: str = "auto"
    target_note_types: dict[str, str] = field(
        default_factory=lambda: dict(_DEFAULT_TARGETS)
    )


def load_config(path: str | Path | None) -> Config:
    """Load Config from a TOML file, or return defaults if it's absent/None."""
    if path is None:
        return Config()
    path = Path(path)
    if not path.exists():
        return Config()

    with path.open("rb") as fh:
        data = tomllib.load(fh)

    anki = _table(data, "anki")
    decks = _table(data, "decks")
    tags = _table(data, "tags")
    targets = _table(data, "target_note_types")
    defaults = Config()
    config = Config(
        ankiconnect_url=anki.get("ankiconnect_url", defaults.ankiconnect_url),
        sync_after_import=anki.get("sync_after_import", defaults.sync_after_import),
        default_deck=decks.get("default_deck", defaults.default_deck),
        auto_tag=tags.get("auto_tag", defaults.auto_tag),
        target_note_types={
            **_DEFAULT_TARGETS,
            **targets,
        },
    )
    _validate_config(config)
    return config


def _table(data: dict[str, object], name: str) -> dict[str, object]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ConfigError(f"{name} must be a TOML table")
    return value


def _validate_config(config: Config) -> None:
    if not isinstance(config.ankiconnect_url, str) or not config.ankiconnect_url.strip():
        raise ConfigError("anki.ankiconnect_url must be a non-empty string")
    if not isinstance(config.sync_after_import, bool):
        raise ConfigError("anki.sync_after_import must be true or false")
    if not isinstance(config.default_deck, str) or not config.default_deck.strip():
        raise ConfigError("decks.default_deck must be a non-empty string")
    if (
        not isinstance(config.auto_tag, str)
        or not config.auto_tag.strip()
        or any(char.isspace() for char in config.auto_tag)
    ):
        raise ConfigError("tags.auto_tag must be one non-empty Anki tag")
    for fact_type, model in config.target_note_types.items():
        if fact_type not in _DEFAULT_TARGETS:
            raise ConfigError(f"unknown target fact type: {fact_type!r}")
        if not isinstance(model, str) or not model.strip():
            raise ConfigError(
                f"target_note_types.{fact_type} must be a non-empty string"
            )
