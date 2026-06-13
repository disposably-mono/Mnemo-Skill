"""Tests for the .apkg fallback backend (scripts/genanki_export.py).

These exercise the genanki-backed exporter without a live Anki: we build real
genanki objects and write a real .apkg, then assert on the resulting package
(a zip containing an Anki collection) and on the intermediate mapping helpers.
"""

import zipfile
import json

import pytest

from scripts.adapter import AnkiNote
from scripts.genanki_export import (
    ExportResult,
    export_apkg,
    stable_id,
    to_genanki_note,
)
from scripts.note_types import MONO_BASIC, MONO_CLOZE


def _basic_note(**over):
    base = dict(
        model="MONO Basic",
        deck="Geography",
        fields={"Front": "Capital of Australia?", "Back": "Canberra",
                "Distractors": "", "Source": "atlas.md"},
        tags=["geo", "auto"],
    )
    base.update(over)
    return AnkiNote(**base)


def test_stable_id_is_deterministic_and_in_genanki_range():
    first = stable_id("MONO Basic")
    again = stable_id("MONO Basic")
    other = stable_id("MONO Cloze")
    assert first == again            # deterministic across calls/runs
    assert first != other            # distinct names -> distinct ids
    assert 1 << 30 <= first < 1 << 31  # genanki's recommended id range


def test_to_genanki_note_orders_fields_per_note_type():
    note = to_genanki_note(_basic_note(), MONO_BASIC)
    # genanki.Note.fields is a positional list matching the model field order.
    assert note.fields == ["Capital of Australia?", "Canberra", "", "atlas.md"]
    assert note.tags == ["geo", "auto"]


def test_export_writes_valid_apkg(tmp_path):
    out = tmp_path / "session.apkg"
    result = export_apkg([_basic_note()], out)
    assert isinstance(result, ExportResult)
    assert result.path == out
    assert result.count == 1
    assert out.exists() and out.stat().st_size > 0
    # An .apkg is a zip carrying the Anki collection db.
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert any(n.startswith("collection.anki2") for n in names)


def test_export_groups_notes_by_deck(tmp_path):
    notes = [
        _basic_note(deck="Geography"),
        _basic_note(deck="Biology::Lecture 3"),
        _basic_note(deck="Geography"),
    ]
    result = export_apkg(notes, tmp_path / "s.apkg")
    assert result.count == 3
    assert set(result.decks) == {"Geography", "Biology::Lecture 3"}


def test_export_handles_cloze_note_type(tmp_path):
    cloze = AnkiNote(
        model="MONO Cloze",
        deck="Idioms",
        fields={"Text": "They say {{c1::practice}} makes perfect.",
                "Extra": "", "Distractors": "", "Source": ""},
        tags=[],
    )
    result = export_apkg([cloze], tmp_path / "c.apkg")
    assert result.count == 1
    # Sanity: the cloze model is wired as a genanki CLOZE model.
    from scripts.genanki_export import model_for
    import genanki
    assert model_for(MONO_CLOZE).model_type == genanki.Model.CLOZE


def test_export_rejects_unknown_model(tmp_path):
    bad = AnkiNote(model="Nonexistent", deck="X", fields={"a": "b"}, tags=[])
    with pytest.raises(KeyError):
        export_apkg([bad], tmp_path / "x.apkg")


def test_export_packages_bundled_fonts(tmp_path):
    out = tmp_path / "fonts.apkg"
    export_apkg([_basic_note()], out)
    with zipfile.ZipFile(out) as zf:
        media = json.loads(zf.read("media"))
    assert "_dmserifdisplay-regular.ttf" in media.values()
    assert "_outfit-variable.ttf" in media.values()
