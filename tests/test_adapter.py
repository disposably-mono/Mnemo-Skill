"""Tests for the Fact -> Anki note adapter (scripts/adapter.py)."""

from scripts.card_schema import Fact
import pytest

from scripts.adapter import AnkiNote, MappingError, adapt, load_mappings


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


# --- mappings.toml interop (Phase 2) ---------------------------------------

def test_no_mappings_falls_back_to_mono_default():
    # An empty mapping (or None) must preserve the MONO behavior exactly.
    assert adapt(_qa(), mappings={}).model == "MONO Basic"
    assert adapt(_qa(), mappings=None).model == "MONO Basic"


def test_mapping_targets_stock_basic_note_type():
    mappings = {"qa": {"Basic": {"Front": "{front}", "Back": "{back}"}}}
    note = adapt(_qa(), mappings=mappings)
    assert note.model == "Basic"
    assert note.fields == {"Front": "Capital of Australia?", "Back": "Canberra"}
    assert note.deck == "Geography"
    assert note.tags == ["geo", "auto"]


def test_mapping_distractors_placeholder_renders_confusions():
    mappings = {"qa": {"Basic": {"Front": "{front}",
                                 "Back": "{back}{distractors}"}}}
    fact = _qa(distractors=[{"text": "Sydney", "grade": "near"}])
    note = adapt(fact, mappings=mappings)
    assert "Canberra" in note.fields["Back"]
    assert "Sydney" in note.fields["Back"]
    assert "confusions" in note.fields["Back"]


def test_mapping_for_cloze_targets_stock_cloze():
    mappings = {"cloze": {"Cloze": {"Text": "{text}", "Back Extra": "{extra}"}}}
    fact = Fact.from_dict({
        "type": "cloze",
        "content": {"text": "Water is {{c1::H2O}}.", "extra": "chemistry"},
        "deck": "Chem", "tags": [],
    })
    note = adapt(fact, mappings=mappings)
    assert note.model == "Cloze"
    assert note.fields["Text"] == "Water is {{c1::H2O}}."
    assert note.fields["Back Extra"] == "chemistry"


def test_mapping_list_items_placeholder_renders_overlapping_cloze():
    mappings = {"list": {"Custom": {"Header": "{title}", "Body": "{items}"}}}
    fact = Fact.from_dict({
        "type": "list",
        "content": {"title": "Planets", "items": ["Mercury", "Venus", "Earth"]},
        "deck": "Astro", "tags": [],
    })
    note = adapt(fact, mappings=mappings)
    assert note.model == "Custom"
    assert note.fields["Header"] == "Planets"
    assert "{{c1::Mercury}}" in note.fields["Body"]
    assert "{{c3::Earth}}" in note.fields["Body"]


def test_only_mapped_fact_types_are_overridden():
    # qa is remapped; cloze has no override so it stays MONO.
    mappings = {"qa": {"Basic": {"Front": "{front}", "Back": "{back}"}}}
    cloze = Fact.from_dict({
        "type": "cloze",
        "content": {"text": "Sky is {{c1::blue}}."},
        "deck": "X", "tags": [],
    })
    assert adapt(cloze, mappings=mappings).model == "MONO Cloze"


def test_load_mappings_parses_nested_toml(tmp_path):
    toml = tmp_path / "mappings.toml"
    toml.write_text(
        '[qa."Basic"]\n'
        'Front = "{front}"\n'
        'Back = "{back}"\n'
        '[cloze."Cloze"]\n'
        'Text = "{text}"\n'
    )
    mappings = load_mappings(toml)
    assert mappings["qa"]["Basic"] == {"Front": "{front}", "Back": "{back}"}
    assert mappings["cloze"]["Cloze"]["Text"] == "{text}"


def test_load_mappings_missing_file_returns_empty(tmp_path):
    assert load_mappings(tmp_path / "absent.toml") == {}
    assert load_mappings(None) == {}


def test_mapping_common_placeholders_include_provenance():
    mappings = {
        "qa": {
            "Custom": {
                "Meta": "{deck}|{tags}|{source}",
            }
        }
    }
    fact = _qa(source="atlas.md")
    note = adapt(fact, mappings)
    assert note.fields["Meta"] == "Geography|geo auto|atlas.md"


def test_unknown_mapping_placeholder_is_rejected():
    mappings = {"qa": {"Custom": {"Front": "{frnot}"}}}
    with pytest.raises(MappingError, match="frnot"):
        adapt(_qa(), mappings)


def test_load_mappings_rejects_unknown_fact_type(tmp_path):
    toml = tmp_path / "mappings.toml"
    toml.write_text('[mcq."Basic"]\nFront = "{front}"\n')
    with pytest.raises(MappingError, match="mcq"):
        load_mappings(toml)


def test_configured_target_selects_matching_mapping():
    mappings = {
        "qa": {
            "Basic": {"Front": "{front}", "Back": "{back}"},
            "Community": {"Question": "{front}", "Answer": "{back}"},
        }
    }
    note = adapt(_qa(), mappings, target_models={"qa": "Community"})
    assert note.model == "Community"
    assert note.fields == {
        "Question": "Capital of Australia?",
        "Answer": "Canberra",
    }


def test_configured_external_target_requires_mapping():
    with pytest.raises(MappingError, match="Missing Model"):
        adapt(_qa(), {}, target_models={"qa": "Missing Model"})
