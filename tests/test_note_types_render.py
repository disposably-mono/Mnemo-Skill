"""Tests for rendering a Card into per-note-type Anki fields (note_types.py)."""

import pytest

from mnemo.anki.note_types import MONO_NOTE_TYPES, RenderError, note_type_for, render_fields
from mnemo.card import Card


def test_qa_card_targets_mono_basic():
    assert note_type_for("qa") == MONO_NOTE_TYPES["MONO Basic"]


def test_cloze_card_targets_mono_cloze():
    assert note_type_for("cloze") == MONO_NOTE_TYPES["MONO Cloze"]


def test_list_card_targets_mono_overlapping():
    assert note_type_for("list") == MONO_NOTE_TYPES["MONO Overlapping"]


def test_typed_card_targets_mono_type():
    assert note_type_for("typed") == MONO_NOTE_TYPES["MONO Type"]


def test_reverse_and_image_supported_target_mono_basic():
    assert note_type_for("reverse") == MONO_NOTE_TYPES["MONO Basic"]
    assert note_type_for("image-supported") == MONO_NOTE_TYPES["MONO Basic"]


def test_render_fields_for_qa_card():
    card = Card(
        front="What is ATP?", back="Adenosine triphosphate.",
        extra="Explanation: it stores energy.", card_type="qa",
        source="notes.md", card_id="c1",
    )
    fields = render_fields(card, MONO_NOTE_TYPES["MONO Basic"])

    assert fields["Front"] == "What is ATP?"
    assert fields["Back"] == "Adenosine triphosphate."
    assert fields["Extra"] == "Explanation: it stores energy."
    assert fields["Mnemonic"] == ""
    assert fields["Source"] == "notes.md"
    assert fields["CardID"] == "c1"
    assert set(fields) == set(MONO_NOTE_TYPES["MONO Basic"].fields)


def test_render_fields_includes_mnemonic_when_present():
    card = Card(
        front="What is ATP?", back="Adenosine triphosphate.",
        mnemonic="A-T-P: Any Time Power", card_type="qa",
    )
    fields = render_fields(card, MONO_NOTE_TYPES["MONO Basic"])
    assert fields["Back"] == "Adenosine triphosphate."
    assert fields["Mnemonic"] == "A-T-P: Any Time Power"


def test_render_fields_for_cloze_card():
    card = Card(
        front="The {{c1::mitochondrion}} produces ATP.",
        back="mitochondrion",
        extra="Explanation: oxidative phosphorylation.",
        card_type="cloze",
    )
    fields = render_fields(card, MONO_NOTE_TYPES["MONO Cloze"])
    assert fields["Text"] == card.front
    assert fields["Extra"] == "Explanation: oxidative phosphorylation."


@pytest.mark.parametrize(
    ("card_type", "note_type_name"),
    [("qa", "MONO Basic"), ("cloze", "MONO Cloze"),
     ("typed", "MONO Type"), ("list", "MONO Overlapping")],
)
def test_render_fields_keeps_yaml_explanation_and_mnemonic_verbatim(card_type, note_type_name):
    card = Card(
        front="Question", back="first; second" if card_type == "list" else "Answer",
        extra="  Why it works.\nSecond line  ", mnemonic="  Memory hook  ",
        card_type=card_type,
    )
    note_type = MONO_NOTE_TYPES[note_type_name]
    fields = render_fields(card, note_type)
    assert fields["Extra"] == "  Why it works.\nSecond line  "
    assert fields["Mnemonic"] == "  Memory hook  "
    assert set(fields) == set(note_type.fields)
    if card_type in ("qa", "typed"):
        assert fields["Back" if card_type == "qa" else "Answer"] == card.back


def test_render_fields_for_typed_card():
    card = Card(front="Formula for water?", back="H2O", card_type="typed")
    fields = render_fields(card, MONO_NOTE_TYPES["MONO Type"])
    assert fields["Prompt"] == "Formula for water?"
    assert fields["Answer"] == "H2O"


def test_render_fields_for_list_card_clozes_each_item():
    card = Card(
        front="Organelles in a cell?",
        back="mitochondrion; nucleus; ribosome",
        card_type="list",
        topic="Cell Biology",
    )
    fields = render_fields(card, MONO_NOTE_TYPES["MONO Overlapping"])

    assert fields["Title"] == "Cell Biology"
    assert "{{c1::mitochondrion}}" in fields["Text"]
    assert "{{c2::nucleus}}" in fields["Text"]
    assert "{{c3::ribosome}}" in fields["Text"]


def test_render_fields_output_matches_declared_fields_exactly():
    card = Card(front="What is ATP?", back="Adenosine triphosphate.", card_type="typed")
    note_type = MONO_NOTE_TYPES["MONO Type"]
    fields = render_fields(card, note_type)
    assert set(fields) == set(note_type.fields)


def test_render_fields_revision_hash_is_present_but_empty_string():
    card = Card(front="What is ATP?", back="Adenosine triphosphate.")
    fields = render_fields(card, MONO_NOTE_TYPES["MONO Basic"])
    assert fields["RevisionHash"] == ""


def test_render_fields_list_card_escapes_literal_braces_in_items():
    card = Card(
        front="What organelles are listed?",
        back="{{c1::injected}}; nucleus",
        card_type="list",
    )
    fields = render_fields(card, MONO_NOTE_TYPES["MONO Overlapping"])

    # The injected braces must not create a second, attacker-controlled
    # cloze deletion -- only the two legitimate items (c1, c2) exist.
    assert fields["Text"].count("{{c") == 2
    assert "&#123;&#123;" in fields["Text"]
    assert "{{c2::nucleus}}" in fields["Text"]


def test_render_fields_list_card_with_no_items_raises():
    card = Card(front="What is listed?", back="; ; ", card_type="list")
    with pytest.raises(RenderError, match="no items"):
        render_fields(card, MONO_NOTE_TYPES["MONO Overlapping"])
