"""Tests for the bundled MONO note types (mnemo/anki/note_types.py)."""

from mnemo.anki.note_types import (
    MONO_BASIC,
    MONO_CLOZE,
    MONO_NOTE_TYPES,
    MONO_OVERLAPPING,
    MONO_TYPE,
    referenced_fields,
)


def test_mono_note_types_registry_has_all_four():
    assert set(MONO_NOTE_TYPES) == {
        "MONO Basic", "MONO Cloze", "MONO Overlapping", "MONO Type",
    }


def test_every_note_type_includes_revision_hash_field():
    # This field was historically missing on fresh Anki profiles and had to
    # be added post-hoc via AnkiConnect; baking it into the field list here
    # is the fix (see mnemo-project memory / feedback history).
    for note_type in MONO_NOTE_TYPES.values():
        assert "RevisionHash" in note_type.fields


def test_every_note_type_includes_card_id_and_source_fields():
    for note_type in MONO_NOTE_TYPES.values():
        assert "CardID" in note_type.fields
        assert "Source" in note_type.fields


def test_mono_cloze_and_overlapping_are_marked_cloze():
    assert MONO_CLOZE.is_cloze is True
    assert MONO_OVERLAPPING.is_cloze is True
    assert MONO_BASIC.is_cloze is False
    assert MONO_TYPE.is_cloze is False


def test_every_template_only_references_declared_fields():
    for note_type in MONO_NOTE_TYPES.values():
        for template in note_type.templates:
            refs = referenced_fields(template.qfmt) | referenced_fields(template.afmt)
            unknown = refs - set(note_type.fields)
            assert not unknown, f"{note_type.name}/{template.name} references undeclared {unknown}"


def test_referenced_fields_strips_section_markers_and_filters():
    text = "{{#Extra}}{{Extra}}{{/Extra}}{{FrontSide}}{{cloze:Text}}{{type:Answer}}"
    assert referenced_fields(text) == {"Extra", "Text", "Answer"}


def test_referenced_fields_ignores_builtin_tokens():
    assert referenced_fields("{{FrontSide}}{{Tags}}{{Deck}}") == set()
