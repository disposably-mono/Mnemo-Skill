"""Runtime configuration loaded from an optional ``config.toml``.

Everything has a sensible default (see ``config.example.toml``), so the
toolkit runs with no config at all. A present file overrides only the keys it
sets; the rest fall back to the defaults below.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_URL = "http://localhost:8765"

# The canonical card-type -> default MONO note-type registry. "reverse" and
# "image-supported" both render into MONO Basic (a source image is embedded
# inline in Front/Back HTML, not a dedicated field; "reverse" adds a second
# Anki card template on the same note type rather than a distinct one).
DEFAULT_CARD_TARGETS = {
    "qa": "MONO Basic",
    "cloze": "MONO Cloze",
    "list": "MONO Overlapping",
    "typed": "MONO Type",
    "reverse": "MONO Basic",
    "image-supported": "MONO Basic",
}

VALID_SCHEDULERS = {"fsrs"}


class ConfigError(ValueError):
    """Raised when config.toml contains an invalid setting."""


@dataclass
class Config:
    """Resolved settings for an import run."""

    ankiconnect_url: str = DEFAULT_URL
    sync_after_import: bool = True
    default_deck: str = "Inbox"
    auto_tag: str = "auto"
    scheduler: str = "fsrs"
    desired_retention: float = 0.9
    new_cards_per_day: int = 20
    card_targets: dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_CARD_TARGETS)
    )


def load_config(path: str | Path | None) -> Config:
    """Load Config from a TOML file, or return defaults if it's absent/None."""
    if path is None:
        return Config()
    path = Path(path)
    if not path.exists():
        return Config()

    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path} is not valid TOML: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"{path} could not be read: {exc}") from exc

    anki = _table(data, "anki")
    decks = _table(data, "decks")
    tags = _table(data, "tags")
    scheduler_table = _table(data, "scheduler")
    targets = _table(data, "card_targets")
    defaults = Config()
    config = Config(
        ankiconnect_url=anki.get("ankiconnect_url", defaults.ankiconnect_url),
        sync_after_import=anki.get("sync_after_import", defaults.sync_after_import),
        default_deck=decks.get("default_deck", defaults.default_deck),
        auto_tag=tags.get("auto_tag", defaults.auto_tag),
        scheduler=scheduler_table.get("scheduler", defaults.scheduler),
        desired_retention=scheduler_table.get(
            "desired_retention", defaults.desired_retention
        ),
        new_cards_per_day=scheduler_table.get(
            "new_cards_per_day", defaults.new_cards_per_day
        ),
        card_targets={
            **DEFAULT_CARD_TARGETS,
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
    _validate_ankiconnect_url(config.ankiconnect_url)
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
    if config.scheduler not in VALID_SCHEDULERS:
        raise ConfigError(
            f"scheduler.scheduler must be one of {sorted(VALID_SCHEDULERS)}"
        )
    if (
        not isinstance(config.desired_retention, (int, float))
        or isinstance(config.desired_retention, bool)
        or not (0.0 < config.desired_retention <= 1.0)
    ):
        raise ConfigError("scheduler.desired_retention must be in (0.0, 1.0]")
    if (
        not isinstance(config.new_cards_per_day, int)
        or isinstance(config.new_cards_per_day, bool)
        or config.new_cards_per_day <= 0
    ):
        raise ConfigError("scheduler.new_cards_per_day must be a positive integer")
    for card_type, model in config.card_targets.items():
        if card_type not in DEFAULT_CARD_TARGETS:
            raise ConfigError(f"unknown card target type: {card_type!r}")
        if not isinstance(model, str) or not model.strip():
            raise ConfigError(f"card_targets.{card_type} must be a non-empty string")


def _validate_ankiconnect_url(url: str) -> None:
    parsed = urlparse(url)
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "http" or parsed.hostname not in local_hosts:
        raise ConfigError(
            "anki.ankiconnect_url must be an http URL on localhost, 127.0.0.1, or ::1"
        )
