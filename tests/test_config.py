"""Tests for runtime config loading (scripts/config.py).

config.toml is optional: a missing file yields documented defaults, and a
partial file overrides only the keys it sets (merged over defaults).
"""

import pytest

from scripts.config import Config, ConfigError, load_config


def test_defaults_when_no_file(tmp_path):
    cfg = load_config(tmp_path / "absent.toml")
    assert cfg == Config()
    assert cfg.ankiconnect_url == "http://localhost:8765"
    assert cfg.sync_after_import is True
    assert cfg.default_deck == "Inbox"
    assert cfg.auto_tag == "auto"
    assert cfg.target_note_types == {
        "qa": "MONO Basic",
        "cloze": "MONO Cloze",
        "list": "MONO Overlapping",
        "typed": "MONO Type",
        "image_occlusion": "Image Occlusion",
    }


def test_loads_values_from_toml(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text(
        "[anki]\n"
        'ankiconnect_url = "http://localhost:9999"\n'
        "sync_after_import = false\n"
        "[decks]\n"
        'default_deck = "Scratch"\n'
        "[tags]\n"
        'auto_tag = "mnemo"\n'
    )
    cfg = load_config(toml)
    assert cfg.ankiconnect_url == "http://localhost:9999"
    assert cfg.sync_after_import is False
    assert cfg.default_deck == "Scratch"
    assert cfg.auto_tag == "mnemo"


def test_partial_target_note_types_merge_over_defaults(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text('[target_note_types]\nqa = "Basic"\n')
    cfg = load_config(toml)
    # Overridden key takes the new value; untouched keys keep defaults.
    assert cfg.target_note_types["qa"] == "Basic"
    assert cfg.target_note_types["cloze"] == "MONO Cloze"
    assert cfg.target_note_types["list"] == "MONO Overlapping"


def test_none_path_yields_defaults():
    assert load_config(None) == Config()


def test_invalid_auto_tag_is_rejected(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text('[tags]\nauto_tag = "two words"\n')
    with pytest.raises(ConfigError, match="auto_tag"):
        load_config(toml)


def test_unknown_target_fact_type_is_rejected(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text('[target_note_types]\nmcq = "Basic"\n')
    with pytest.raises(ConfigError, match="mcq"):
        load_config(toml)


def test_non_table_section_is_rejected(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text('tags = "auto"\n')
    with pytest.raises(ConfigError, match="tags must be a TOML table"):
        load_config(toml)
