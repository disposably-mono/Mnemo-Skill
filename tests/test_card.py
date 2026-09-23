"""Validation tests for the Card domain object."""

import pytest

from mnemo.card import CARD_TYPES, Card, CardValidationError


def make_card(**overrides):
    return Card(**({"front": "What produces ATP?", "back": "Mitochondria."} | overrides))


def test_card_types_match_supported_values():
    assert CARD_TYPES == ("qa", "cloze", "reverse", "typed", "list", "image-supported")


@pytest.mark.parametrize("field,value", [("front", ""), ("back", "   "), ("front", 5)])
def test_required_text_is_validated(field, value):
    with pytest.raises(CardValidationError, match=field):
        make_card(**{field: value})


def test_unknown_card_type_is_rejected():
    with pytest.raises(CardValidationError, match="card_type"):
        make_card(card_type="multiple-choice")


def test_front_over_150_characters_is_rejected():
    with pytest.raises(CardValidationError, match="150 characters"):
        make_card(front="a" * 151)


def test_front_of_exactly_150_characters_is_accepted():
    assert make_card(front="a" * 150).front == "a" * 150


def test_particle_heavy_tagalog_front_within_char_limit_is_accepted():
    front = (
        "Ang ginagamit sa pagtuturo sa pag-aaral sa mga eskuwelahan at ang "
        "wika sa pagsulat ng mga aklat at kagamitan sa pagtuturo sa silid-aralan"
    )
    assert len(front.split()) == 23
    assert make_card(front=front).front == front


@pytest.mark.parametrize("tags", [["two words"], [3], "biology"])
def test_invalid_tags_are_rejected(tags):
    with pytest.raises(CardValidationError, match="tag"):
        make_card(tags=tags)


@pytest.mark.parametrize("confidence", [-0.01, 1.01, True, "0.5"])
def test_invalid_confidence_is_rejected(confidence):
    with pytest.raises(CardValidationError, match="confidence"):
        make_card(confidence=confidence)


def test_confidence_bounds_are_accepted():
    assert make_card(confidence=0).confidence == 0
    assert make_card(confidence=1).confidence == 1


def test_cloze_card_type_is_accepted():
    assert make_card(card_type="cloze", front="{{c1::mitochondrion}} produces ATP.").card_type == "cloze"
