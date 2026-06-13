"""Tests for the MONO reference note types (scripts/note_types.py)."""

from scripts.note_types import (
    MONO_BASIC,
    MONO_CLOZE,
    MONO_NOTE_TYPES,
    MONO_OVERLAPPING,
    referenced_fields,
)

EXPECTED_NAMES = {"MONO Basic", "MONO Cloze", "MONO Overlapping"}


def test_registry_has_the_three_v1_note_types():
    assert set(MONO_NOTE_TYPES) == EXPECTED_NAMES
    for name, nt in MONO_NOTE_TYPES.items():
        assert nt.name == name


def test_every_note_type_has_fields_and_templates():
    for nt in MONO_NOTE_TYPES.values():
        assert len(nt.fields) >= 2, nt.name
        assert len(nt.templates) >= 1, nt.name
        assert nt.css.strip(), nt.name


def test_templates_only_reference_declared_fields():
    for nt in MONO_NOTE_TYPES.values():
        declared = set(nt.fields)
        for tpl in nt.templates:
            for side in (tpl.qfmt, tpl.afmt):
                missing = referenced_fields(side) - declared
                assert not missing, f"{nt.name}/{tpl.name} references {missing}"


def test_cloze_flags_are_correct():
    assert MONO_CLOZE.is_cloze is True
    assert MONO_OVERLAPPING.is_cloze is True
    assert MONO_BASIC.is_cloze is False


def test_cloze_models_use_cloze_replacement():
    for nt in (MONO_CLOZE, MONO_OVERLAPPING):
        assert any("cloze:" in t.qfmt for t in nt.templates), nt.name


def test_basic_and_cloze_carry_a_distractors_field():
    assert "Distractors" in MONO_BASIC.fields
    assert "Distractors" in MONO_CLOZE.fields
    # Overlapping (lists) intentionally has no distractors.
    assert "Distractors" not in MONO_OVERLAPPING.fields


def test_design_system_port_is_present_in_css():
    css = MONO_BASIC.css
    # Night-mode mapping (dark theme) per Anki convention, not [data-theme].
    assert ".nightMode" in css
    assert "data-theme" not in css
    # Design-system fonts and a signature palette color (fern accent).
    assert "DM Serif Display" in css
    assert "Outfit" in css
    assert "DM Mono" in css
    assert "#588157" in css  # fern (dark-theme accent)


def test_referenced_fields_ignores_builtins_and_handles_prefixes():
    text = "{{FrontSide}} {{Front}} {{cloze:Text}} {{#Distractors}}{{Distractors}}{{/Distractors}} {{Tags}}"
    assert referenced_fields(text) == {"Front", "Text", "Distractors"}
