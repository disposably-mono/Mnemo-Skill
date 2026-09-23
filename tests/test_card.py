"""Tests for the Card CSV contract (mnemo/card.py).

Card is the intermediate format shared by draft -> author -> audit -> import.
Required fields per SKILL.md: Front, Back, Extra, Mnemonic, CardType, Tags,
plus Image/Topic/Source/CardID/Confidence for traceability and validation.
"""

import pytest

from mnemo.card import (
    Card,
    CardValidationError,
    CARD_TYPES,
    read_cards,
    write_cards,
)


def make_card(**overrides):
    fields = dict(
        front="What organelle produces most cellular ATP?",
        back="The mitochondrion.",
        extra="Explanation: oxidative phosphorylation occurs there.",
        mnemonic="",
        card_type="qa",
        tags=["biology", "cell-respiration"],
    )
    fields.update(overrides)
    return Card(**fields)


def test_card_types_match_skill_contract():
    assert CARD_TYPES == ("qa", "cloze", "reverse", "typed", "list", "image-supported")


def test_valid_card_round_trips_through_csv(tmp_path):
    card = make_card()
    csv_path = tmp_path / "cards.csv"
    write_cards(csv_path, [card])
    loaded = read_cards(csv_path)
    assert loaded == [card]


def test_write_then_read_preserves_optional_fields(tmp_path):
    card = make_card(
        image="mitochondrion.png",
        topic="Cell Biology",
        source="module01.md#L12",
        card_id="c-0001",
        confidence=0.92,
    )
    csv_path = tmp_path / "cards.csv"
    write_cards(csv_path, [card])
    loaded = read_cards(csv_path)
    assert loaded == [card]
    assert loaded[0].confidence == pytest.approx(0.92)


def test_missing_optional_fields_default_sensibly(tmp_path):
    csv_path = tmp_path / "cards.csv"
    write_cards(csv_path, [make_card()])
    loaded = read_cards(csv_path)
    assert loaded[0].image is None
    assert loaded[0].topic is None
    assert loaded[0].source is None
    assert loaded[0].card_id is None
    assert loaded[0].confidence is None


def test_tags_round_trip_as_space_separated(tmp_path):
    card = make_card(tags=["biology", "cell-respiration", "atp"])
    csv_path = tmp_path / "cards.csv"
    write_cards(csv_path, [card])
    text = csv_path.read_text()
    assert "biology cell-respiration atp" in text
    loaded = read_cards(csv_path)
    assert loaded[0].tags == ["biology", "cell-respiration", "atp"]


def test_empty_front_is_rejected():
    with pytest.raises(CardValidationError, match="front"):
        make_card(front="")


def test_empty_back_is_rejected():
    with pytest.raises(CardValidationError, match="back"):
        make_card(back="   ")


def test_unknown_card_type_is_rejected():
    with pytest.raises(CardValidationError, match="card_type"):
        make_card(card_type="multiple-choice")


def test_front_over_20_words_is_rejected():
    long_front = " ".join(["word"] * 21)
    with pytest.raises(CardValidationError, match="20 words"):
        make_card(front=long_front)


def test_front_of_exactly_20_words_is_accepted():
    front20 = " ".join(["word"] * 20)
    card = make_card(front=front20)
    assert card.front == front20


def test_tag_containing_whitespace_is_rejected():
    with pytest.raises(CardValidationError, match="tag"):
        make_card(tags=["two words"])


def test_confidence_out_of_range_is_rejected():
    with pytest.raises(CardValidationError, match="confidence"):
        make_card(confidence=1.5)


def test_read_cards_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_cards(tmp_path / "absent.csv")


def test_read_cards_on_empty_file_returns_empty_list(tmp_path):
    csv_path = tmp_path / "cards.csv"
    write_cards(csv_path, [])
    assert read_cards(csv_path) == []


def test_cloze_card_type_is_accepted():
    card = make_card(card_type="cloze", front="{{c1::mitochondrion}} produces ATP.")
    assert card.card_type == "cloze"
