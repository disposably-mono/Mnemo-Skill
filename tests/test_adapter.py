"""Tests for the Fact -> Anki note adapter (scripts/adapter.py)."""

from scripts.card_schema import Fact
from scripts.adapter import AnkiNote, adapt


def _qa(**over):
    base = {
        "type": "qa",
        "content": {"front": "Capital of Australia?", "back": "Canberra"},
        "deck": "Geography",
        "tags": ["geo", "auto"],
        "source": "atlas.md",
    }
    base.update(over)
    return Fact.from_dict(base)


def test_qa_maps_to_mono_basic():
    note = adapt(_qa())
    assert isinstance(note, AnkiNote)
    assert note.model == "MONO Basic"
    assert note.deck == "Geography"
    assert note.tags == ["geo", "auto"]
    assert note.fields["Front"] == "Capital of Australia?"
    assert note.fields["Back"] == "Canberra"
    assert note.fields["Source"] == "atlas.md"
    assert note.fields["Distractors"] == ""  # none provided


def test_qa_without_source_yields_empty_source_field():
    note = adapt(_qa(source=None))
    assert note.fields["Source"] == ""


def test_qa_distractors_render_grouped_confusions():
    fact = _qa(distractors=[
        {"text": "Sydney", "grade": "near"},
        {"text": "Melbourne", "grade": "near"},
        {"text": "Auckland", "grade": "far"},
    ])
    html = adapt(fact).fields["Distractors"]
    assert "confusions" in html
    assert "Sydney" in html and "Melbourne" in html and "Auckland" in html
    # graded classes present for color coding
    assert 'class="near"' in html
    assert 'class="far"' in html
    # near group should come before far group (weighted toward plausible)
    assert html.index("Sydney") < html.index("Auckland")


def test_cloze_maps_to_mono_cloze():
    fact = Fact.from_dict({
        "type": "cloze",
        "content": {"text": "They say {{c1::practice}} makes {{c2::perfect}}.",
                    "extra": "an idiom"},
        "deck": "Idioms",
        "tags": [],
    })
    note = adapt(fact)
    assert note.model == "MONO Cloze"
    assert note.fields["Text"] == "They say {{c1::practice}} makes {{c2::perfect}}."
    assert note.fields["Extra"] == "an idiom"


def test_list_becomes_overlapping_cloze():
    fact = Fact.from_dict({
        "type": "list",
        "content": {"title": "Steps of mitosis",
                    "items": ["Prophase", "Metaphase", "Anaphase", "Telophase"]},
        "deck": "Biology",
        "tags": ["bio"],
        "source": "ch5.pdf p.2",
    })
    note = adapt(fact)
    assert note.model == "MONO Overlapping"
    assert note.fields["Title"] == "Steps of mitosis"
    text = note.fields["Text"]
    # one cloze per item, sequentially numbered, hiding each in turn
    assert "{{c1::Prophase}}" in text
    assert "{{c2::Metaphase}}" in text
    assert "{{c4::Telophase}}" in text
    assert note.fields["Source"] == "ch5.pdf p.2"


def test_unknown_grade_group_absent_when_empty():
    # only 'near' distractors -> no medium/far list items
    fact = _qa(distractors=[{"text": "Sydney", "grade": "near"}])
    html = adapt(fact).fields["Distractors"]
    assert 'class="medium"' not in html
    assert 'class="far"' not in html
