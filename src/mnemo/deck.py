"""Strict, versioned YAML manifests for Mnemo decks."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

from mnemo.card import Card, CardValidationError

FORMAT_VERSION = 1
ROOT_FIELDS = frozenset({"formatVersion", "deck", "cards"})
DECK_FIELDS = frozenset({"name", "tags"})
CARD_FIELDS = frozenset({
    "id", "front", "back", "extra", "mnemonic", "cardType", "tags",
    "image", "topic", "source", "confidence",
})


class DeckFormatError(ValueError):
    """Raised when a deck manifest does not satisfy the format contract."""


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects repeated mapping keys."""


def _construct_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        try:
            is_duplicate = key in result
        except TypeError as exc:
            raise DeckFormatError("YAML mapping keys must be scalar") from exc
        if is_duplicate:
            raise DeckFormatError(f"duplicate key {key!r} in YAML mapping")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def _require_mapping(value: Any, location: str, allowed: frozenset[str]) -> dict:
    if not isinstance(value, dict):
        raise DeckFormatError(f"{location} must be a mapping")
    unknown = value.keys() - allowed
    if unknown:
        raise DeckFormatError(f"unknown {location} field(s): {', '.join(sorted(map(str, unknown)))}")
    return value


def _require_name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeckFormatError("deck name must be a non-empty string")
    return value


def _require_tags(value: Any, location: str) -> list[str]:
    if not isinstance(value, list):
        raise DeckFormatError(f"{location} tags must be a list")
    for tag in value:
        if not isinstance(tag, str) or not tag or any(char.isspace() for char in tag):
            raise DeckFormatError(f"{location} tag {tag!r} must be a single non-empty word")
    return value


def _validate_cards(cards: Any) -> list[Card]:
    if not isinstance(cards, list):
        raise DeckFormatError("cards must be a list")
    seen_ids: set[str] = set()
    for index, card in enumerate(cards):
        if not isinstance(card, Card):
            raise DeckFormatError(f"cards[{index}] must be a card")
        try:
            replace(card)
        except CardValidationError as exc:
            raise DeckFormatError(f"cards[{index}]: {exc}") from exc
        if not isinstance(card.card_id, str) or not card.card_id.strip():
            raise DeckFormatError(f"cards[{index}] id must be a non-empty string")
        if card.card_id in seen_ids:
            raise DeckFormatError(f"duplicate card id {card.card_id!r}")
        seen_ids.add(card.card_id)
    return cards


@dataclass
class Deck:
    """A named collection of authored cards and shared tags."""

    name: str
    cards: list[Card]
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_name(self.name)
        _require_tags(self.tags, "deck")
        _validate_cards(self.cards)


def _parse_card(value: Any, index: int) -> Card:
    location = f"cards[{index}]"
    data = _require_mapping(value, location, CARD_FIELDS)
    for required in ("id", "front", "back"):
        if required not in data:
            raise DeckFormatError(f"{location} missing {required}")
    try:
        return Card(
            card_id=data["id"], front=data["front"], back=data["back"],
            extra=data.get("extra", ""), mnemonic=data.get("mnemonic", ""),
            card_type=data.get("cardType", "qa"), tags=data.get("tags", []),
            image=data.get("image"), topic=data.get("topic"),
            source=data.get("source"), confidence=data.get("confidence"),
        )
    except CardValidationError as exc:
        raise DeckFormatError(f"{location}: {exc}") from exc


def read_deck(path: str | Path) -> Deck:
    """Read and validate one YAML deck manifest."""
    with Path(path).open(encoding="utf-8") as handle:
        try:
            raw = yaml.load(handle, Loader=_UniqueKeyLoader)
        except yaml.YAMLError as exc:
            raise DeckFormatError(f"invalid YAML: {exc}") from exc
    root = _require_mapping(raw, "root", ROOT_FIELDS)
    if type(root.get("formatVersion")) is not int or root["formatVersion"] != FORMAT_VERSION:
        raise DeckFormatError(f"formatVersion must be {FORMAT_VERSION}")
    metadata = _require_mapping(root.get("deck"), "deck", DECK_FIELDS)
    name = _require_name(metadata.get("name"))
    tags = _require_tags(metadata.get("tags", []), "deck")
    raw_cards = root.get("cards")
    if not isinstance(raw_cards, list):
        raise DeckFormatError("cards must be a list")
    cards = [_parse_card(value, index) for index, value in enumerate(raw_cards)]
    return Deck(name=name, cards=cards, tags=tags)


def _serialize_card(card: Card) -> dict[str, Any]:
    return {
        "id": card.card_id, "front": card.front, "back": card.back,
        "extra": card.extra, "mnemonic": card.mnemonic,
        "cardType": card.card_type, "tags": card.tags,
        "image": card.image, "topic": card.topic, "source": card.source,
        "confidence": card.confidence,
    }


def write_deck(path: str | Path, deck: Deck) -> None:
    """Write a validated deck as a UTF-8 YAML manifest."""
    if not isinstance(deck, Deck):
        raise DeckFormatError("deck must be a Deck")
    deck.__post_init__()
    document = {
        "formatVersion": FORMAT_VERSION,
        "deck": {"name": deck.name, "tags": deck.tags},
        "cards": [_serialize_card(card) for card in deck.cards],
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8")


def cards_for_import(deck: Deck) -> list[Card]:
    """Copy cards with deck tags prepended, preserving each original card."""
    return [
        replace(card, tags=list(dict.fromkeys([*deck.tags, *card.tags])))
        for card in deck.cards
    ]
