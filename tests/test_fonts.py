"""Tests for bundled font resolution and media dedup (mnemo/anki/fonts.py)."""

from pathlib import Path

import pytest

from mnemo.anki.fonts import bundled_font_paths, unique_media_paths


def test_bundled_font_paths_returns_all_ttf_files():
    paths = bundled_font_paths()
    names = {p.name for p in paths}
    assert names == {
        "_dmmono-medium.ttf", "_dmmono-regular.ttf",
        "_dmserifdisplay-regular.ttf", "_outfit-variable.ttf",
    }


def test_bundled_font_paths_are_real_readable_files():
    for path in bundled_font_paths():
        assert path.exists()
        assert path.stat().st_size > 0


def test_unique_media_paths_deduplicates_by_filename(tmp_path):
    f = tmp_path / "a.png"
    f.write_bytes(b"x")
    result = unique_media_paths([f, f])
    assert result == [f]


def test_unique_media_paths_rejects_name_collision_with_different_files(tmp_path):
    a = tmp_path / "one" / "shared.png"
    b = tmp_path / "two" / "shared.png"
    a.parent.mkdir()
    b.parent.mkdir()
    a.write_bytes(b"a")
    b.write_bytes(b"b")

    with pytest.raises(ValueError, match="shared.png"):
        unique_media_paths([a, b])


def test_unique_media_paths_with_empty_input():
    assert unique_media_paths([]) == []
