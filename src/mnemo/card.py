"""Validated flashcard values shared by drafting, auditing, and importing."""

from __future__ import annotations

from dataclasses import dataclass, field

CARD_TYPES: tuple[str, ...] = (
    "qa",
    "cloze",
    "reverse",
    "typed",
    "list",
    "image-supported",
)

# Character length, not word count: word count isn't a portable proxy for
# recall load across languages. Particle-heavy languages (e.g. Tagalog's
# short "sa"/"ng"/"ang"/"mga"/"at"/"na") inflate word count for the same
# semantic complexity an English sentence expresses in fewer, denser words.
# 150 chars comfortably fits a real single-clause Tagalog front while still
# forcing genuine splitting of multi-clause prose (which runs 300+ chars).
_MAX_FRONT_CHARS = 150


class CardValidationError(ValueError):
    """Raised when a Card violates the required contract."""


@dataclass
class Card:
    """A single draft or authored flashcard."""

    front: str
    back: str
    extra: str = ""
    mnemonic: str = ""
    card_type: str = "qa"
    tags: list[str] = field(default_factory=list)
    image: str | None = None
    topic: str | None = None
    source: str | None = None
    card_id: str | None = None
    confidence: float | None = None

    def __post_init__(self) -> None:
        _validate_card(self)


def _validate_card(card: Card) -> None:
    if not isinstance(card.front, str) or not card.front.strip():
        raise CardValidationError("front must be a non-empty string")
    if not isinstance(card.back, str) or not card.back.strip():
        raise CardValidationError("back must be a non-empty string")
    for name in ("extra", "mnemonic"):
        if not isinstance(getattr(card, name), str):
            raise CardValidationError(f"{name} must be a string")
    if card.card_type not in CARD_TYPES:
        raise CardValidationError(f"card_type must be one of {CARD_TYPES}")
    for name in ("image", "topic", "source", "card_id"):
        value = getattr(card, name)
        if value is not None and not isinstance(value, str):
            raise CardValidationError(f"{name} must be a string or null")
    if len(card.front) > _MAX_FRONT_CHARS:
        raise CardValidationError(f"front must be at most {_MAX_FRONT_CHARS} characters")
    if not isinstance(card.tags, list):
        raise CardValidationError("tags must be a list")
    for tag in card.tags:
        if not isinstance(tag, str) or not tag or any(char.isspace() for char in tag):
            raise CardValidationError(f"tag {tag!r} must be a single non-empty word")
    if card.confidence is not None and (
        isinstance(card.confidence, bool)
        or not isinstance(card.confidence, (int, float))
        or not (0.0 <= card.confidence <= 1.0)
    ):
        raise CardValidationError("confidence must be between 0.0 and 1.0")
