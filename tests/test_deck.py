"""YAML deck manifest contract tests."""

import pytest

from mnemo.card import Card
from mnemo.deck import Deck, DeckFormatError, cards_for_import, read_deck, write_deck


def make_card(**overrides):
    return Card(**({"front": "What is ATP?", "back": "Adenosine triphosphate.", "card_id": "c-1"} | overrides))


def test_deck_round_trips_through_yaml(tmp_path):
    deck = Deck(name="Mnemo::Biology", tags=["biology"], cards=[make_card(
        extra="Explanation", mnemonic="Energy", tags=["cells"], image="atp.png",
        topic="Cell biology", source="module.md#L12", confidence=0.92,
    )])
    path = tmp_path / "biology.mnemo.yaml"
    write_deck(path, deck)
    assert read_deck(path) == deck
    assert "formatVersion: 1" in path.read_text()
    assert "cardType: qa" in path.read_text()


def test_write_deck_creates_parent_and_supports_empty_cards(tmp_path):
    path = tmp_path / "nested" / "empty.mnemo.yaml"
    write_deck(path, Deck(name="Biology", cards=[]))
    assert read_deck(path) == Deck(name="Biology", cards=[])


def test_read_deck_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_deck(tmp_path / "absent.mnemo.yaml")


def test_duplicate_card_ids_are_rejected(tmp_path):
    path = tmp_path / "bad.mnemo.yaml"
    path.write_text("formatVersion: 1\ndeck: {name: Biology}\ncards:\n- {id: c-1, front: A, back: B}\n- {id: c-1, front: C, back: D}\n")
    with pytest.raises(DeckFormatError, match="duplicate card id"):
        read_deck(path)


@pytest.mark.parametrize("yaml_text,expected", [
    ("formatVersion: 1\nformatVersion: 1\ndeck: {name: Biology}\ncards: []\n", "duplicate key"),
    ("formatVersion: 1\ndeck: {name: Biology, name: Chemistry}\ncards: []\n", "duplicate key"),
    ("formatVersion: 1\ndeck: {name: Biology}\ncards:\n- {id: x, front: A, front: C, back: B}\n", "duplicate key"),
    ("formatVersion: 2\ndeck: {name: Biology}\ncards: []\n", "formatVersion"),
    ("formatVersion: true\ndeck: {name: Biology}\ncards: []\n", "formatVersion"),
    ("deck: {name: Biology}\ncards: []\n", "formatVersion"),
    ("formatVersion: 1\ndeck: {name: Biology}\ncards: []\nextra: x\n", "unknown"),
    ("formatVersion: 1\ndeck: {name: Biology, other: x}\ncards: []\n", "unknown"),
    ("formatVersion: 1\ndeck: {name: Biology}\ncards:\n- {id: x, front: A, back: B, other: x}\n", "unknown"),
    ("formatVersion: 1\ndeck: {}\ncards: []\n", "name"),
    ("formatVersion: 1\ndeck: {name: '  '}\ncards: []\n", "name"),
    ("formatVersion: 1\ndeck: {name: Biology}\ncards: x\n", "cards"),
    ("formatVersion: 1\ndeck: {name: Biology}\n", "cards"),
    ("formatVersion: 1\ndeck: {name: Biology}\ncards: [x]\n", "cards"),
    ("formatVersion: 1\ndeck: {name: Biology}\ncards:\n- {front: A, back: B}\n", "id"),
    ("formatVersion: 1\ndeck: {name: Biology}\ncards:\n- {id: x, front: A}\n", "back"),
    ("formatVersion: 1\ndeck: {name: Biology}\ncards:\n- {id: x, front: A, back: B, confidence: true}\n", "confidence"),
    ("formatVersion: 1\ndeck: {name: Biology}\ncards:\n- {id: x, front: A, back: B, confidence: 1.1}\n", "confidence"),
    ("formatVersion: 1\ndeck: {name: Biology, tags: wrong}\ncards: []\n", "tags"),
    ("formatVersion: 1\ndeck: {name: Biology}\ncards:\n- {id: x, front: A, back: B, tags: [good, 'two words']}\n", "tag"),
    ("formatVersion: 1\ndeck: {name: Biology}\ncards: [\n", "YAML"),
])
def test_invalid_manifest_is_rejected(tmp_path, yaml_text, expected):
    path = tmp_path / "bad.mnemo.yaml"
    path.write_text(yaml_text)
    with pytest.raises(DeckFormatError, match=expected):
        read_deck(path)


def test_cards_for_import_merges_tags_without_mutating_deck():
    card = make_card(tags=["shared", "card"])
    deck = Deck(name="Biology", tags=["deck", "shared"], cards=[card])
    imported = cards_for_import(deck)
    assert imported == [make_card(tags=["deck", "shared", "card"])]
    assert imported[0] is not card
    assert deck.cards == [make_card(tags=["shared", "card"])]
    assert deck.tags == ["deck", "shared"]


def test_writer_rejects_card_that_became_invalid_after_deck_creation(tmp_path):
    deck = Deck(name="Biology", cards=[make_card()])
    deck.cards[0].confidence = True
    with pytest.raises(DeckFormatError, match="confidence"):
        write_deck(tmp_path / "bad.mnemo.yaml", deck)
