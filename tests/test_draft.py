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


def test_definition_line_generates_both_requested_directions():
    cards, deferred = draft_cards(
        [Chunk(text="Wika: Isang sistema ng mga simbolo.", source="notes.md")],
        directions="both",
    )

    assert deferred == []
    assert [(card.front, card.back) for card in cards] == [
        ("What is wika?", "Isang sistema ng mga simbolo."),
        ("What is the term for Isang sistema ng mga simbolo?", "Wika"),
    ]


def test_definition_line_can_generate_term_to_definition_only():
    cards, deferred = draft_cards(
        [Chunk(text="Wika: Isang sistema ng mga simbolo.", source="notes.md")],
        directions="term-to-definition",
    )

    assert deferred == []
    assert [(card.front, card.back) for card in cards] == [
        ("What is wika?", "Isang sistema ng mga simbolo.")
    ]


def test_definition_line_can_generate_definition_to_term_only():
    cards, deferred = draft_cards(
        [Chunk(text="Wika: Isang sistema ng mga simbolo.", source="notes.md")],
        directions="definition-to-term",
    )

    assert deferred == []
    assert [(card.front, card.back) for card in cards] == [
        ("What is the term for Isang sistema ng mga simbolo?", "Wika")
    ]


def test_qa_input_is_not_reversed_when_both_directions_are_requested():
    cards, _ = draft_cards(
        [Chunk(text="Q: What is ATP?\nA: Adenosine triphosphate.", source="notes.md")],
        directions="both",
    )

    assert [(card.front, card.back) for card in cards] == [
        ("What is ATP?", "Adenosine triphosphate.")
    ]


def test_draft_cards_rejects_unknown_direction():
    import pytest

    with pytest.raises(ValueError, match="directions"):
        draft_cards([], directions="reverse")


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


def test_lettered_section_header_sets_topic(tmp_path=None):
    text = "A. Wikang Panturo\n\nQ: Ano ang wikang panturo?\nA: Ang ginagamit sa pagtuturo.\n"
    cards, deferred = draft_cards([Chunk(text=text, source="wika.md")])

    assert deferred == []
    assert cards[0].topic == "Wikang Panturo"


def test_lettered_section_header_splits_from_preceding_paragraph_with_no_blank_line():
    text = (
        "Some closing sentence of the previous section.\n"
        "B. Varayti ng Wika\n"
        "\n"
        "Q: Ano ang dayalek?\n"
        "A: Heograpikal na varayti ng wika.\n"
    )
    cards, deferred = draft_cards([Chunk(text=text, source="wika.md")])

    assert len(deferred) == 1
    assert deferred[0].text == "Some closing sentence of the previous section."
    assert len(cards) == 1
    assert cards[0].topic == "Varayti ng Wika"


def test_single_capital_letter_sentence_is_not_treated_as_section_header():
    # "A. Reyes" (an abbreviated name) must not be mistaken for a lettered
    # section header just because it matches "<capital letter>. <text>".
    text = "A. Reyes ang pangalan ng may-akda ng aklat na ito.\n"
    cards, deferred = draft_cards([Chunk(text=text, source="wika.md")])

    assert cards == []
    assert len(deferred) == 1
    assert "A. Reyes" in deferred[0].text


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


def test_overlong_grounded_front_defers_instead_of_crashing():
    # A Q:/A: block that matches the grounding pattern but whose front fails
    # Card's own validation (too long) must defer that block, not raise an
    # uncaught exception that kills the whole draft_cards() run.
    long_front = "word " * 40
    text = f"Q: {long_front.strip()}?\nA: short answer\n"

    cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])

    assert cards == []
    assert len(deferred) == 1
    assert "failed validation" in deferred[0].reason


def test_one_overlong_card_does_not_lose_other_grounded_cards_in_the_same_chunk():
    long_front = "word " * 40
    text = (
        f"Q: {long_front.strip()}?\nA: short answer\n"
        "\n"
        "Q: What is ATP?\nA: Adenosine triphosphate.\n"
    )

    cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])

    assert len(cards) == 1
    assert cards[0].front == "What is ATP?"
    assert len(deferred) == 1


def test_stem_bullets_with_mixed_non_bullet_line_is_deferred():
    text = "Organelles:\n- mitochondrion\nnot a bullet\n- ribosome\n"
    cards, deferred = draft_cards([Chunk(text=text, source="notes.md")])
    assert cards == []
    assert len(deferred) == 1
