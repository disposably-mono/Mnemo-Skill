"""The Card CSV contract: the intermediate format between every pipeline stage.

Per SKILL.md's Required Card Contract, a card carries the six required Anki
fields (Front, Back, Extra, Mnemonic, CardType, Tags) plus optional
traceability fields (Image, Topic, Source, CardID, Confidence). The
deterministic drafter emits cards, the agent authors/rewrites them in place,
the audit rubric validates them, and the importer reads the same CSV.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

CARD_TYPES: tuple[str, ...] = (
    "qa",
    "cloze",
    "reverse",
    "typed",
    "list",
    "image-supported",
)

_MAX_FRONT_WORDS = 20
_FIELDNAMES = (
    "Front",
    "Back",
    "Extra",
    "Mnemonic",
    "CardType",
    "Tags",
    "Image",
    "Topic",
    "Source",
    "CardID",
    "Confidence",
)


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
    if not card.front.strip():
        raise CardValidationError("front must be a non-empty string")
    if not card.back.strip():
        raise CardValidationError("back must be a non-empty string")
    if card.card_type not in CARD_TYPES:
        raise CardValidationError(f"card_type must be one of {CARD_TYPES}")
    if len(card.front.split()) > _MAX_FRONT_WORDS:
        raise CardValidationError(f"front must be at most {_MAX_FRONT_WORDS} words")
    for tag in card.tags:
        if not tag or any(char.isspace() for char in tag):
            raise CardValidationError(f"tag {tag!r} must be a single non-empty word")
    if card.confidence is not None and not (0.0 <= card.confidence <= 1.0):
        raise CardValidationError("confidence must be between 0.0 and 1.0")


def write_cards(path: str | Path, cards: list[Card]) -> None:
    """Write cards to a CSV file, creating parent directories as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_FIELDNAMES)
        writer.writeheader()
        for card in cards:
            writer.writerow(_card_to_row(card))


def read_cards(path: str | Path) -> list[Card]:
    """Read cards from a CSV file previously written by write_cards()."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return [_row_to_card(row) for row in reader]


def _card_to_row(card: Card) -> dict[str, str]:
    return {
        "Front": card.front,
        "Back": card.back,
        "Extra": card.extra,
        "Mnemonic": card.mnemonic,
        "CardType": card.card_type,
        "Tags": " ".join(card.tags),
        "Image": card.image or "",
        "Topic": card.topic or "",
        "Source": card.source or "",
        "CardID": card.card_id or "",
        "Confidence": "" if card.confidence is None else str(card.confidence),
    }


def _row_to_card(row: dict[str, str]) -> Card:
    confidence = row.get("Confidence") or ""
    return Card(
        front=row["Front"],
        back=row["Back"],
        extra=row.get("Extra", ""),
        mnemonic=row.get("Mnemonic", ""),
        card_type=row.get("CardType", "qa"),
        tags=(row.get("Tags") or "").split(),
        image=row.get("Image") or None,
        topic=row.get("Topic") or None,
        source=row.get("Source") or None,
        card_id=row.get("CardID") or None,
        confidence=float(confidence) if confidence else None,
    )
