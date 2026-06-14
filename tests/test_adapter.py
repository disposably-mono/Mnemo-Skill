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


def test_mapping_common_placeholders_include_semantic_metadata():
    mappings = {
        "qa": {
            "Custom": {
                "Meta": "{knowledge_unit_id}|{knowledge_kind}|{objective_ids}|{origin}|{confidence}",
            }
        }
    }
    fact = _qa(
        knowledge_unit_id="unit-1",
        knowledge_kind="comparison",
        objective_ids=["objective-1"],
        origin="source",
        confidence=0.9,
    )

    assert adapt(fact, mappings).fields["Meta"] == (
        "unit-1|comparison|objective-1|source|0.9"
    )


def test_unknown_mapping_placeholder_is_rejected():
    mappings = {"qa": {"Custom": {"Front": "{frnot}"}}}
    with pytest.raises(MappingError, match="frnot"):
        adapt(_qa(), mappings)


def test_mapping_value_containing_a_token_is_not_re_substituted():
    # A field value that literally contains another field's {token} must be
    # filled in a single pass — the inner {back} stays verbatim.
    mappings = {"qa": {"Basic": {"Front": "{front}", "Back": "{back}"}}}
    fact = _qa(content={"front": "see {back} below", "back": "Canberra"})
    note = adapt(fact, mappings)
    assert note.fields["Front"] == "see {back} below"
    assert note.fields["Back"] == "Canberra"


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


def test_typed_fact_targets_mono_type_and_splits_hints():
    fact = Fact.from_dict({
        "type": "typed",
        "content": {
            "prompt": "Formula for water?",
            "answer": "H2O",
            "hints": ["Three characters", "Starts with H"],
            "extra": "Two hydrogen atoms and one oxygen atom.",
        },
        "deck": "Chem",
        "tags": [],
    })
    note = adapt(fact)
    assert note.model == "MONO Type"
    assert note.fields["Hint 1"] == "Three characters"
    assert note.fields["Hint 2"] == "Starts with H"
    assert note.fields["Hint 3"] == ""


def test_image_occlusion_builds_native_fields_and_media(tmp_path):
    image = tmp_path / "heart.png"
    image.write_bytes(b"image")
    fact = Fact.from_dict({
        "type": "image_occlusion",
        "content": {
            "image": "heart.png",
            "header": "Heart anatomy",
            "masks": [
                {"shape": "rect", "left": 0.1, "top": 0.2,
                 "width": 0.3, "height": 0.1},
            ],
        },
        "deck": "Anatomy",
        "tags": [],
    })
    note = adapt(fact, media_root=tmp_path)
    assert note.model == "Image Occlusion"
    assert note.fields["Image"] == '<img src="heart.png">'
    assert "{{c1::image-occlusion:rect" in note.fields["Occlusion"]
    assert ":oi=1" in note.fields["Occlusion"]
    assert note.media == [image]


def test_image_occlusion_can_group_masks_on_one_card(tmp_path):
    image = tmp_path / "heart.png"
    image.write_bytes(b"image")
    fact = Fact.from_dict({
        "type": "image_occlusion",
        "content": {
            "image": "heart.png",
            "masks": [
                {"shape": "rect", "left": 0.1, "top": 0.2,
                 "width": 0.2, "height": 0.1, "card": 1},
                {"shape": "rect", "left": 0.5, "top": 0.2,
                 "width": 0.2, "height": 0.1, "card": 1},
            ],
        },
        "deck": "Anatomy",
        "tags": [],
    })
    occlusion = adapt(fact, media_root=tmp_path).fields["Occlusion"]
    assert occlusion.count("{{c1::") == 2
    assert "{{c2::" not in occlusion


def test_mapped_image_occlusion_keeps_media_upload(tmp_path):
    image = tmp_path / "heart.png"
    image.write_bytes(b"image")
    fact = Fact.from_dict({
        "type": "image_occlusion",
        "content": {
            "image": "heart.png",
            "masks": [
                {"shape": "rect", "left": 0.1, "top": 0.2,
                 "width": 0.3, "height": 0.1},
            ],
        },
        "deck": "Anatomy",
        "tags": [],
    })
    mappings = {
        "image_occlusion": {
            "Bildverdeckung": {
                "Bild": "{image}",
                "Verdeckung": "{occlusion}",
            }
        }
    }
    note = adapt(
        fact,
        mappings,
        target_models={"image_occlusion": "Bildverdeckung"},
        media_root=tmp_path,
    )
    assert note.fields["Bild"] == '<img src="heart.png">'
    assert note.media == [image]
