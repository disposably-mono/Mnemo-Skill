"""Tests for runtime config loading (mnemo/config.py).

config.toml is optional: a missing file yields documented defaults, and a
partial file overrides only the keys it sets (merged over defaults).
"""

import pytest

from mnemo.config import Config, ConfigError, DEFAULT_CARD_TARGETS, load_config


def test_defaults_when_no_file(tmp_path):
    cfg = load_config(tmp_path / "absent.toml")
    assert cfg == Config()
    assert cfg.ankiconnect_url == "http://localhost:8765"
    assert cfg.sync_after_import is True
    assert cfg.default_deck == "Inbox"
    assert cfg.auto_tag == "auto"
    assert cfg.scheduler == "fsrs"
    assert cfg.desired_retention == 0.9
    assert cfg.new_cards_per_day == 20
    assert cfg.card_targets == {
        "qa": "MONO Basic",
        "cloze": "MONO Cloze",
        "list": "MONO Overlapping",
        "typed": "MONO Type",
        "reverse": "MONO Basic",
        "image-supported": "MONO Basic",
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
        "[scheduler]\n"
        "desired_retention = 0.85\n"
        "new_cards_per_day = 10\n"
    )
    cfg = load_config(toml)
    assert cfg.ankiconnect_url == "http://localhost:9999"
    assert cfg.sync_after_import is False
    assert cfg.default_deck == "Scratch"
    assert cfg.auto_tag == "mnemo"
    assert cfg.desired_retention == 0.85
    assert cfg.new_cards_per_day == 10


def test_rejects_non_local_ankiconnect_url(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text('[anki]\nankiconnect_url = "https://example.com/anki"\n')

    with pytest.raises(ConfigError, match="localhost"):
        load_config(toml)


def test_partial_card_targets_merge_over_defaults(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text('[card_targets]\nqa = "Basic"\n')
    cfg = load_config(toml)
    assert cfg.card_targets["qa"] == "Basic"
    assert cfg.card_targets["cloze"] == "MONO Cloze"
    assert cfg.card_targets["list"] == "MONO Overlapping"


def test_none_path_yields_defaults():
    assert load_config(None) == Config()


def test_default_card_targets_is_public_and_owned_by_config():
    assert DEFAULT_CARD_TARGETS == {
        "qa": "MONO Basic",
        "cloze": "MONO Cloze",
        "list": "MONO Overlapping",
        "typed": "MONO Type",
        "reverse": "MONO Basic",
        "image-supported": "MONO Basic",
    }
    assert Config().card_targets == DEFAULT_CARD_TARGETS


def test_invalid_auto_tag_is_rejected(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text('[tags]\nauto_tag = "two words"\n')
    with pytest.raises(ConfigError, match="auto_tag"):
        load_config(toml)


def test_unknown_card_target_type_is_rejected(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text('[card_targets]\nmcq = "Basic"\n')
    with pytest.raises(ConfigError, match="mcq"):
        load_config(toml)


def test_non_table_section_is_rejected(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text('tags = "auto"\n')
    with pytest.raises(ConfigError, match="tags must be a TOML table"):
        load_config(toml)


def test_desired_retention_out_of_range_is_rejected(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text("[scheduler]\ndesired_retention = 1.5\n")
    with pytest.raises(ConfigError, match="desired_retention"):
        load_config(toml)


def test_new_cards_per_day_must_be_positive(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text("[scheduler]\nnew_cards_per_day = 0\n")
    with pytest.raises(ConfigError, match="new_cards_per_day"):
        load_config(toml)


def test_unknown_scheduler_is_rejected(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text('[scheduler]\nscheduler = "sm2"\n')
    with pytest.raises(ConfigError, match="scheduler"):
        load_config(toml)


def test_desired_retention_boolean_is_rejected(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text("[scheduler]\ndesired_retention = true\n")
    with pytest.raises(ConfigError, match="desired_retention"):
        load_config(toml)


def test_desired_retention_boundaries(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text("[scheduler]\ndesired_retention = 0.0\n")
    with pytest.raises(ConfigError, match="desired_retention"):
        load_config(toml)

    toml.write_text("[scheduler]\ndesired_retention = 1.0\n")
    assert load_config(toml).desired_retention == 1.0


def test_ankiconnect_url_scheme_rejected_independently_of_host(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text('[anki]\nankiconnect_url = "https://localhost:8765"\n')
    with pytest.raises(ConfigError, match="ankiconnect_url"):
        load_config(toml)


def test_ankiconnect_url_accepts_127_0_0_1_and_ipv6(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text('[anki]\nankiconnect_url = "http://127.0.0.1:8765"\n')
    assert load_config(toml).ankiconnect_url == "http://127.0.0.1:8765"

    toml.write_text('[anki]\nankiconnect_url = "http://[::1]:8765"\n')
    assert load_config(toml).ankiconnect_url == "http://[::1]:8765"


def test_empty_ankiconnect_url_is_rejected(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text('[anki]\nankiconnect_url = ""\n')
    with pytest.raises(ConfigError, match="ankiconnect_url"):
        load_config(toml)


def test_non_bool_sync_after_import_is_rejected(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text('[anki]\nsync_after_import = "yes"\n')
    with pytest.raises(ConfigError, match="sync_after_import"):
        load_config(toml)


def test_empty_default_deck_is_rejected(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text('[decks]\ndefault_deck = "   "\n')
    with pytest.raises(ConfigError, match="default_deck"):
        load_config(toml)


def test_empty_card_target_model_is_rejected(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text('[card_targets]\nqa = ""\n')
    with pytest.raises(ConfigError, match="card_targets"):
        load_config(toml)


def test_malformed_toml_raises_config_error(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text("this is not [ valid toml")
    with pytest.raises(ConfigError, match="not valid TOML"):
        load_config(toml)
