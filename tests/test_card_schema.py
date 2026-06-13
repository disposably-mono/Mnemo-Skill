"""Tests for the Fact contract + validation (scripts/card_schema.py)."""

import pytest

from scripts.card_schema import (
    CardValidationError,
    Distractor,
    Fact,
    dump_facts,
    load_facts,
)


# --- Construction / valid cases ---------------------------------------------

def test_valid_qa_fact():
    fact = Fact.from_dict(
        {
            "type": "qa",
            "content": {"front": "What is the powerhouse of the cell?",
                        "back": "The mitochondrion"},
            "deck": "Biology::Lecture 3",
            "tags": ["biology", "lecture-3"],
            "source": "lecture3.pdf p.4",
        }
    )
    assert fact.type == "qa"
    assert fact.content["back"] == "The mitochondrion"
    assert fact.distractors == []


def test_valid_cloze_fact():
    fact = Fact.from_dict(
        {
            "type": "cloze",
            "content": {"text": "They say that {{c1::practice}} makes {{c2::perfect}}."},
            "deck": "Idioms",
            "tags": ["idioms"],
        }
    )
    assert fact.type == "cloze"
    assert fact.source is None


def test_valid_list_fact():
    fact = Fact.from_dict(
        {
            "type": "list",
            "content": {
                "title": "Steps of mitosis",
                "items": ["Prophase", "Metaphase", "Anaphase", "Telophase"],
            },
            "deck": "Biology",
            "tags": ["biology"],
        }
    )
    assert fact.content["items"][0] == "Prophase"


def test_valid_typed_fact_with_progressive_hints():
    fact = Fact.from_dict({
        "type": "typed",
        "content": {
            "prompt": "Chemical formula for water?",
            "answer": "H2O",
            "hints": ["Three characters", "Starts with H"],
        },
        "deck": "Chemistry",
        "tags": [],
    })
    assert fact.content["hints"] == ["Three characters", "Starts with H"]


def test_valid_image_occlusion_fact():
    fact = Fact.from_dict({
        "type": "image_occlusion",
        "content": {
            "image": "heart.png",
            "masks": [
                {"shape": "rect", "left": 0.1, "top": 0.2,
                 "width": 0.3, "height": 0.1},
                {"shape": "ellipse", "left": 0.5, "top": 0.3,
                 "rx": 0.1, "ry": 0.08},
            ],
        },
        "deck": "Anatomy",
        "tags": [],
    })
    assert len(fact.content["masks"]) == 2


def test_qa_fact_with_graded_distractors():
    fact = Fact.from_dict(
        {
            "type": "qa",
            "content": {"front": "Capital of Australia?", "back": "Canberra"},
            "deck": "Geography",
            "tags": ["geo"],
            "distractors": [
                {"text": "Sydney", "grade": "near"},
                {"text": "Melbourne", "grade": "near"},
                {"text": "Auckland", "grade": "far"},
            ],
        }
    )
    assert len(fact.distractors) == 3
    assert isinstance(fact.distractors[0], Distractor)
    assert fact.distractors[2].grade == "far"


# --- Invalid cases ----------------------------------------------------------

def test_unknown_type_rejected():
    with pytest.raises(CardValidationError, match="type"):
        Fact.from_dict({"type": "mcq", "content": {}, "deck": "D", "tags": []})


def test_qa_missing_back_rejected():
    with pytest.raises(CardValidationError, match="back"):
        Fact.from_dict(
            {"type": "qa", "content": {"front": "Q only"}, "deck": "D", "tags": []}
        )


def test_qa_empty_front_rejected():
    with pytest.raises(CardValidationError):
        Fact.from_dict(
            {"type": "qa", "content": {"front": "   ", "back": "A"},
             "deck": "D", "tags": []}
        )


def test_cloze_without_marker_rejected():
    with pytest.raises(CardValidationError, match="cloze"):
        Fact.from_dict(
            {"type": "cloze", "content": {"text": "no deletion here"},
             "deck": "D", "tags": []}
        )


def test_list_requires_at_least_two_items():
    with pytest.raises(CardValidationError, match="items"):
        Fact.from_dict(
            {"type": "list", "content": {"title": "T", "items": ["only one"]},
             "deck": "D", "tags": []}
        )


def test_distractor_bad_grade_rejected():
    with pytest.raises(CardValidationError, match="grade"):
        Fact.from_dict(
            {
                "type": "qa",
                "content": {"front": "Q", "back": "A"},
                "deck": "D",
                "tags": [],
                "distractors": [{"text": "X", "grade": "sorta"}],
            }
        )


def test_distractors_not_allowed_on_list():
    with pytest.raises(CardValidationError, match="distractor"):
        Fact.from_dict(
            {
                "type": "list",
                "content": {"title": "T", "items": ["a", "b"]},
                "deck": "D",
                "tags": [],
                "distractors": [{"text": "X", "grade": "near"}],
            }
        )


def test_typed_supports_at_most_three_hints():
    with pytest.raises(CardValidationError, match="three hints"):
        Fact.from_dict({
            "type": "typed",
            "content": {"prompt": "Q", "answer": "A", "hints": ["1", "2", "3", "4"]},
            "deck": "D",
            "tags": [],
        })


def test_image_occlusion_rejects_out_of_bounds_mask():
    with pytest.raises(CardValidationError, match="between 0 and 1"):
        Fact.from_dict({
            "type": "image_occlusion",
            "content": {
                "image": "x.png",
                "masks": [{"shape": "rect", "left": 1.2, "top": 0,
                           "width": 0.2, "height": 0.2}],
            },
            "deck": "D",
            "tags": [],
        })


def test_image_occlusion_rejects_invalid_card_group():
    with pytest.raises(CardValidationError, match="positive integer"):
        Fact.from_dict({
            "type": "image_occlusion",
            "content": {
                "image": "x.png",
                "masks": [{"shape": "rect", "left": 0.1, "top": 0.2,
                           "width": 0.2, "height": 0.2, "card": 0}],
            },
            "deck": "D",
            "tags": [],
        })


def test_tags_must_be_a_list_not_a_string():
    with pytest.raises(CardValidationError, match="tags must be a list"):
        Fact.from_dict({
            "type": "qa",
            "content": {"front": "Q", "back": "A"},
            "deck": "D",
            "tags": "auto",
        })


def test_empty_deck_rejected():
    with pytest.raises(CardValidationError, match="deck"):
        Fact.from_dict(
            {"type": "qa", "content": {"front": "Q", "back": "A"},
             "deck": "  ", "tags": []}
        )


def test_tag_with_space_rejected():
    with pytest.raises(CardValidationError, match="tag"):
        Fact.from_dict(
            {"type": "qa", "content": {"front": "Q", "back": "A"},
             "deck": "D", "tags": ["two words"]}
        )


# --- Serialization round-trips ----------------------------------------------

def test_to_dict_from_dict_round_trip():
    src = {
        "type": "qa",
        "content": {"front": "Q", "back": "A"},
        "deck": "D",
        "tags": ["t"],
        "source": "s.md",
        "distractors": [{"text": "X", "grade": "medium"}],
    }
    fact = Fact.from_dict(src)
    assert fact.to_dict() == src


def test_jsonl_dump_and_load_round_trip(tmp_path):
    facts = [
        Fact.from_dict({"type": "qa", "content": {"front": "Q1", "back": "A1"},
                        "deck": "D", "tags": ["t"]}),
        Fact.from_dict({"type": "cloze", "content": {"text": "a {{c1::b}} c"},
                        "deck": "D", "tags": []}),
    ]
    path = tmp_path / "cards.jsonl"
    dump_facts(facts, path)
    loaded = load_facts(path)
    assert [f.to_dict() for f in loaded] == [f.to_dict() for f in facts]


def test_load_facts_applies_deck_and_tag_defaults(tmp_path):
    path = tmp_path / "cards.jsonl"
    path.write_text(
        '{"type":"qa","content":{"front":"Q","back":"A"},'
        '"tags":["existing"]}\n'
    )
    fact = load_facts(path, default_deck="Inbox", auto_tag="mnemo")[0]
    assert fact.deck == "Inbox"
    assert fact.tags == ["existing", "mnemo"]
