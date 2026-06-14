import csv
import json

from scripts.generate_flashcards import (
    GenerationConfig,
    analyze_retention,
    atomic_units,
    build_cards,
    interleave_cards,
    main,
    parse_content,
    validate_deck,
)
from scripts.test_card_quality import build_report


PASSING_NOTES = """\
# Biology
[image: mitochondrion.png | alt: The membrane folds cue where ATP production occurs.]
Mitochondria produce ATP.
ATP synthase uses a proton gradient.
The cell membrane is a phospholipid bilayer.

# Chemistry
Water is H2O.
Sodium chloride is table salt.
Carbon has atomic number six.
"""


def test_parse_and_split_enumeration_with_mnemonic():
    units = parse_content("The primary colors include red, blue, and yellow.")

    assert [unit.answer for unit in units] == ["red", "blue", "yellow"]
    cards = build_cards(units)
    assert all(card.mnemonic == "RBY: red, blue, yellow" for card in cards)


def test_interleave_avoids_adjacent_topics_when_possible():
    cards = build_cards(parse_content(PASSING_NOTES))
    interleaved = interleave_cards(cards, seed=7)

    for index, (previous, current) in enumerate(zip(interleaved, interleaved[1:])):
        if previous.topic == current.topic:
            remaining = interleaved[index + 2 :]
            assert not any(card.topic != current.topic for card in remaining)


def test_passing_deck_meets_required_rubric():
    cards = interleave_cards(build_cards(parse_content(PASSING_NOTES)))
    violations = validate_deck(cards, GenerationConfig())

    assert not [violation for violation in violations if violation.level == "error"]
    assert len({card.card_type for card in cards}) >= 3
    assert any(card.image_url for card in cards)
    assert all(("{{c1::" in card.front) == (card.card_type == "cloze") for card in cards)


def test_text_only_deck_is_blocked():
    cards = build_cards(parse_content("# A\nAlpha is one.\n# B\nBeta is two.\nGamma is three."))

    violations = validate_deck(cards, GenerationConfig())

    assert any(violation.code == "TEXT_ONLY_DECK" for violation in violations)


def test_fsrs_rejects_one_day_learning_step():
    cards = build_cards(parse_content(PASSING_NOTES))
    config = GenerationConfig(scheduler="fsrs")

    violations = validate_deck(cards, config)

    assert any(violation.code == "FSRS_LONG_STEP" for violation in violations)


def test_retention_hook_uses_only_mature_reviews(tmp_path):
    log = tmp_path / "reviews.csv"
    log.write_text(
        "card_id,interval_days,predicted_retention,actual_recalled\n"
        "young,20,0.9,1\n"
        "mature-a,30,0.9,1\n"
        "mature-b,45,0.9,0\n",
        encoding="utf-8",
    )

    report = analyze_retention(log)

    assert report["mature_reviews"] == 2
    assert report["mean_calibration_error"] == -0.4


def test_cli_and_independent_auditor(tmp_path):
    source = tmp_path / "notes.md"
    output = tmp_path / "deck.csv"
    source.write_text(PASSING_NOTES, encoding="utf-8")

    assert main([str(source), "--output", str(output)]) == 0
    report = build_report(output, output.with_suffix(".settings.json"))

    assert report["status"] == "PASS"
    assert output.exists()
    assert output.with_suffix(".violations.json").exists()
    settings = json.loads(output.with_suffix(".settings.json").read_text())
    assert settings["learning_steps"] == ["10m", "1d"]
    assert settings["graduating_interval_days"] == 3
    assert settings["easy_interval_days"] == 7
    assert settings["max_ease_percent"] == 250
    assert settings["new_cards_per_day"] == 20

    with output.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert {"Front", "Back", "Extra", "Mnemonic", "CardType", "Tags"} <= set(rows[0])
