"""Tests for the deterministic drafter (mnemo/draft.py).

Per SKILL.md: the drafter only emits a card when it can ground it confidently
(explicit Q&A, definitions, clean enumerations, simple relations). Anything
else is left deferred for the agent to author -- never a fabricated prompt.
"""

from mnemo.card import Card
from mnemo.draft import DeferredUnit, draft_cards
from mnemo.ingest import Chunk


def test_structured_qa_block_is_grounded():
    text = (
        "Q: What organelle produces most cellular ATP?\n"
        "A: The mitochondrion.\n"
        "Extra: Oxidative phosphorylation occurs there.\n"
        "Tags: biology cell-respiration\n"
    )
    cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])

    assert deferred == []
    assert cards == [
        Card(
            front="What organelle produces most cellular ATP?",
            back="The mitochondrion.",
            extra="Oxidative phosphorylation occurs there.",
            card_type="qa",
            tags=["biology", "cell-respiration"],
            source="notes.md",
        )
    ]


def test_double_colon_pair_is_grounded():
    text = "What is the powerhouse of the cell? :: The mitochondrion."
    cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])

    assert deferred == []
    assert len(cards) == 1
    assert cards[0].front == "What is the powerhouse of the cell?"
    assert cards[0].back == "The mitochondrion."


def test_tab_separated_pair_is_grounded():
    text = "What is ATP?\tAdenosine triphosphate."
    cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])

    assert deferred == []
    assert cards[0].front == "What is ATP?"
    assert cards[0].back == "Adenosine triphosphate."


def test_colon_definition_line_is_grounded():
    text = "Mitochondrion: the organelle that produces most cellular ATP."
    cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])

    assert deferred == []
    assert cards[0].front == "What is mitochondrion?"
    assert cards[0].back == "The organelle that produces most cellular ATP."


def test_stem_with_bullets_is_grounded_as_list():
    text = "Organelles in a cell:\n- mitochondrion\n- nucleus\n- ribosome\n"
    cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])

    assert deferred == []
    assert cards[0].card_type == "list"
    assert cards[0].front == "Organelles in a cell?"
    assert cards[0].back == "mitochondrion; nucleus; ribosome"


def test_heading_sets_topic_for_following_cards():
    text = (
        "# Cell Biology\n\n"
        "Q: What is ATP?\n"
        "A: Adenosine triphosphate.\n"
    )
    cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])

    assert cards[0].topic == "Cell Biology"


def test_topic_line_sets_topic_for_following_cards():
    text = "Topic: Cell Biology\n\nQ: What is ATP?\nA: Adenosine triphosphate.\n"
    cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])

    assert cards[0].topic == "Cell Biology"


def test_unrecognized_prose_is_deferred_not_fabricated():
    text = "Mitochondria have a double membrane structure that is quite complex."
    cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])

    assert cards == []
    assert len(deferred) == 1
    assert isinstance(deferred[0], DeferredUnit)
    assert deferred[0].source == "notes.md"
    assert "double membrane" in deferred[0].text


def test_multiple_blocks_split_on_blank_lines():
    text = (
        "Q: What is ATP?\n"
        "A: Adenosine triphosphate.\n"
        "\n"
        "Some unstructured prose that cannot be grounded confidently here.\n"
    )
    cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])

    assert len(cards) == 1
    assert len(deferred) == 1


def test_deck_and_source_are_attached_to_grounded_cards():
    text = "Q: What is ATP?\nA: Adenosine triphosphate.\n"
    cards, _ = draft_cards([Chunk(text=text, source="lecture.pdf p.3")], deck="Biology")

    assert cards[0].source == "lecture.pdf p.3"


def test_qa_block_without_extra_or_tags_defaults_sensibly():
    text = "Q: What is ATP?\nA: Adenosine triphosphate.\n"
    cards, _ = draft_cards([Chunk(text=text, source="notes.md")])

    assert cards[0].extra == ""
    assert cards[0].tags == []


def test_figure_caption_is_deferred_not_fabricated():
    text = "Figure 3: shows the mitochondria structure in detail."
    cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])
    assert cards == []
    assert len(deferred) == 1


def test_table_caption_is_deferred_not_fabricated():
    text = "Table 1: Summary of results from the trial run."
    cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])
    assert cards == []
    assert len(deferred) == 1


def test_note_and_warning_labels_are_deferred_not_fabricated():
    for text in (
        "Note: see the appendix for details on this topic.",
        "Warning: do not open the reactor door during operation.",
        "See: http://example.com/page for more.",
    ):
        cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])
        assert cards == [], f"unexpected card from: {text!r}"
        assert len(deferred) == 1


def test_overlong_term_is_deferred_not_fabricated():
    text = "This is a very long label with way too many words here: some text."
    cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])
    assert cards == []
    assert len(deferred) == 1


def test_double_colon_wins_over_definition_line_when_both_match():
    text = "Term: something :: rewritten as a pair."
    cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])
    assert deferred == []
    assert cards[0].front == "Term: something"
    assert cards[0].back == "rewritten as a pair."


def test_qa_block_missing_answer_line_is_deferred():
    text = "Q: What is ATP?\nNo answer line here.\n"
    cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])
    assert cards == []
    assert len(deferred) == 1


def test_tab_pair_with_three_parts_is_deferred():
    text = "front\tmiddle\tback"
    cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])
    assert cards == []
    assert len(deferred) == 1


def test_tab_pair_with_empty_part_is_deferred():
    text = "front\t"
    cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])
    assert cards == []
    assert len(deferred) == 1


def test_stem_bullets_with_too_few_bullets_is_deferred():
    text = "Organelles:\n- mitochondrion\n"
    cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])
    assert cards == []
    assert len(deferred) == 1


def test_stem_bullets_with_mixed_non_bullet_line_is_deferred():
    text = "Organelles:\n- mitochondrion\nnot a bullet\n- ribosome\n"
    cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])
    assert cards == []
    assert len(deferred) == 1
