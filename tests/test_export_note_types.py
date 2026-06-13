"""Tests for the shareable MONO note-type installer (scripts/export_note_types.py).

This builds a .apkg holding the MONO note types with one example note each, so a
user can install the styled types into Anki via File -> Import. We assert on the
produced package (a real zip) without a live Anki.
"""

import zipfile

from scripts.export_note_types import export_note_types, main


def test_exports_a_valid_apkg_with_one_example_per_mono_type(tmp_path):
    out = tmp_path / "mono.apkg"
    result = export_note_types(out)

    assert result.path == out
    assert result.count == 3  # Basic, Cloze, Overlapping
    assert out.exists() and out.stat().st_size > 0
    with zipfile.ZipFile(out) as zf:
        assert any(n.startswith("collection.anki2") for n in zf.namelist())


def test_examples_land_in_a_single_install_deck(tmp_path):
    result = export_note_types(tmp_path / "mono.apkg")
    assert len(result.decks) == 1


def test_cli_writes_to_requested_path(tmp_path):
    out = tmp_path / "install-me.apkg"
    code = main(["-o", str(out)])
    assert code == 0
    assert out.exists()
