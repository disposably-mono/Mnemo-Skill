import csv
import json

from scripts.generate_flashcards import (
    Card,
    GenerationConfig,
    analyze_retention,
    atomic_units,
    build_cards,
    interleave_cards,
    main,
    parse_content,
    plan_knowledge,
    split_sentences,
    validate_card,
    validate_deck,
)
from scripts.audit_cards import build_report


def make_card(**changes):
    base = dict(
        front="What is alpha?",
        back="the first letter",
        extra="Explanation: Alpha denotes the first ordinal position. Context: Topic: T.",
        mnemonic="",
        card_type="qa",
        tags=["t"],
        topic="T",
        source="s:line-1",
    )
    base.update(changes)
    return Card(**base)


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
    assert all(len(card.front.split()) < 20 for card in cards)


def test_semicolon_lists_preserve_internal_conjunctions():
    units = parse_content(
        "Q: What are the communication categories?\n"
        "A: Kinesics; Artifacts and Environment; Vocalics or Paralinguistics"
    )

    assert [unit.answer for unit in units] == [
        "Kinesics",
        "Artifacts and Environment",
        "Vocalics or Paralinguistics",
    ]


def test_contrast_and_argument_links_are_not_destroyed_by_atomic_splitting():
    units = parse_content(
        "Market share increased, but profit fell because costs rose.\n\n"
        "The evidence is limited; therefore the conclusion remains uncertain."
    )

    assert len(units) == 2
    assert "but profit fell" in units[0].text
    assert "therefore" in units[1].text


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
    assert any(card.image_url for card in cards)
    assert all(("{{c1::" in card.front) == (card.card_type == "cloze") for card in cards)


def test_text_only_deck_can_pass_without_decorative_media():
    cards = build_cards(parse_content("# A\nAlpha is one.\n# B\nBeta is two.\nGamma is three."))

    violations = validate_deck(cards, GenerationConfig())

    assert not [violation for violation in violations if violation.level == "error"]


def test_reverse_cards_are_limited_to_term_definitions():
    units = parse_content(
        "Q: What is haptics?\nA: Communication through touch.\n\n"
        "Q: Who invented the telegraph?\nA: Samuel Morse."
    )

    cards = build_cards(units)
    reverse_cards = [card for card in cards if card.card_type == "reverse"]

    assert len(reverse_cards) == 1
    assert reverse_cards[0].front == "Which term means: Communication through touch?"
    assert reverse_cards[0].back == "haptics"
    assert all("identify" not in card.front for card in cards)


def test_explicit_questions_are_not_forced_into_cloze_for_variety():
    cards = build_cards(
        parse_content(
            "Q: Who wrote Hamlet?\nA: The playwright William Shakespeare.\n\n"
            "Q: Who painted Guernica?\nA: The artist Pablo Picasso.\n\n"
            "Q: Who developed relativity?\nA: The physicist Albert Einstein."
        )
    )

    assert all(card.card_type != "cloze" for card in cards)


def test_list_component_prompts_are_not_reversed_as_definitions():
    cards = build_cards(
        parse_content(
            "Q: What are the components of the communication model?\n"
            "A: Source, Channel, Receiver"
        )
    )

    assert all(card.card_type != "reverse" for card in cards)
    assert all(card.back != "component 1 of 3 in the communication model" for card in cards)


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
    assert output.with_suffix(".manifest.json").exists()
    assert output.with_suffix(".coverage.json").exists()
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
    assert {"KnowledgeUnitID", "KnowledgeKind", "ObjectiveIDs", "Origin"} <= set(rows[0])


def test_semantic_planning_classifies_mixed_knowledge_and_objectives():
    source = """\
# Strategy
Learning objective: distinguish market penetration from product development
Market penetration differs from product development by focusing on existing products and markets.
Because retention lowers replacement demand, it can reduce acquisition pressure.
After the launch fails, the team revises its positioning.

# Quantitative
Return on investment = net profit / investment cost
"""
    units = parse_content(source, "lecture.md")
    objectives, knowledge = plan_knowledge(units, source, "lecture.md")

    assert any(objective.explicit for objective in objectives)
    assert {unit.kind for unit in knowledge} >= {
        "comparison",
        "mechanism",
        "narrative",
        "formula",
    }
    assert all(unit.objective_ids for unit in knowledge)


def test_objective_blocks_are_not_cards_and_map_conservatively():
    source = """\
# Economics
Objectives:
- Define elasticity
- Compare substitutes and complements

Elasticity is responsiveness to a change in price.
Substitutes differ from complements because demand moves in opposite directions.
"""
    units = parse_content(source, "economics.md")
    objectives, knowledge = plan_knowledge(units, source, "economics.md")

    assert len(objectives) == 2
    assert len(knowledge) == 2
    assert knowledge[0].objective_ids == [objectives[0].id]
    assert knowledge[1].objective_ids == [objectives[1].id]


def test_adjacent_structured_lines_remain_separate_with_line_provenance():
    source = """\
# Metrics
Return on investment = net profit / investment cost
A campaign is effective only when lift exceeds cost.
"""
    units = parse_content(source, "metrics.md")
    _, knowledge = plan_knowledge(units, source, "metrics.md")

    assert [unit.kind for unit in knowledge] == ["formula", "exception"]
    assert [unit.source for unit in knowledge] == ["metrics.md:line-2", "metrics.md:line-3"]


def test_prerequisites_link_only_when_a_defined_term_is_reused():
    source = (
        "Elasticity is responsiveness to a change in price.\n"
        "Elasticity affects how quantity demanded responds.\n"
        "Revenue is price multiplied by quantity."
    )
    units = parse_content(source)
    _, knowledge = plan_knowledge(units, source, "notes.md")

    assert knowledge[1].prerequisite_ids == [knowledge[0].id]
    assert knowledge[2].prerequisite_ids == []


def test_semantic_prompts_preserve_comparison_and_narrative_relations():
    source = (
        "A differs from B because its scope is narrower.\n"
        "After the launch failed, the team revised its positioning."
    )
    units = parse_content(source)
    plan_knowledge(units, source, "input")
    cards = build_cards(units)

    assert cards[0].front == "How does A differ from B?"
    assert cards[0].back == "its scope is narrower"
    assert cards[1].front == "What happens after the launch failed?"
    assert cards[1].back == "the team revised its positioning"


def test_unstructured_fragments_are_deferred_in_manifest(tmp_path):
    source = tmp_path / "fragments.md"
    output = tmp_path / "fragments.csv"
    source.write_text("# Notes\nA contextless fragment\n", encoding="utf-8")

    assert main([str(source), "--output", str(output), "--allow-violations"]) == 0
    manifest = json.loads(output.with_suffix(".manifest.json").read_text())

    assert manifest["knowledge_units"][0]["status"] == "deferred"


def test_independent_auditor_rejects_invalid_objective_status(tmp_path):
    source = tmp_path / "notes.md"
    output = tmp_path / "deck.csv"
    source.write_text("# Topic\nAlpha is one.\n", encoding="utf-8")
    assert main([str(source), "--output", str(output)]) == 0
    coverage_path = output.with_suffix(".coverage.json")
    coverage = json.loads(coverage_path.read_text())
    coverage["objectives"][0]["status"] = "maybe"
    coverage_path.write_text(json.dumps(coverage), encoding="utf-8")

    report = build_report(
        output,
        output.with_suffix(".settings.json"),
        coverage_path=coverage_path,
    )

    assert report["status"] == "FAIL"
    assert any(v["code"] == "COVERAGE_INVALID" for v in report["violations"])


def test_unsplit_set_back_gets_auto_mnemonic_and_passes_mnemonic_rule():
    cards = build_cards(
        parse_content("The three domains of life are Bacteria, Archaea, and Eukarya.")
    )
    card = next(card for card in cards if "Bacteria" in card.back)

    assert card.mnemonic == "BAE: Bacteria, Archaea, Eukarya"
    violations = validate_deck(cards, GenerationConfig())
    assert not any(violation.code == "MISSING_MNEMONIC" for violation in violations)


def test_clausal_compound_back_does_not_demand_a_mnemonic():
    cards = build_cards(
        parse_content("Photosynthesis stores energy, whereas respiration releases it.")
    )

    violations = validate_deck(cards, GenerationConfig())
    assert not any(violation.code == "MISSING_MNEMONIC" for violation in violations)


def test_declarative_fact_with_uncommon_verb_is_not_dropped():
    cards = build_cards(parse_content("Photosynthesis converts light into chemical energy."))

    assert cards
    assert any("Photosynthesis" in card.front for card in cards)


def test_sentence_split_keeps_abbreviations_and_initials_together():
    assert split_sentences("Use a base, e.g. NaOH, in the reaction. Water is wet.") == [
        "Use a base, e.g. NaOH, in the reaction.",
        "Water is wet.",
    ]


def test_thin_explanation_is_flagged_but_does_not_block():
    card = make_card(front="What is X?", back="Y", extra="Explanation: X is Y. Context: Topic: T.")

    violations = validate_card(card)
    codes = {violation.code for violation in violations}
    assert "THIN_EXPLANATION" in codes
    assert all(violation.level == "warning" for violation in violations if violation.code == "THIN_EXPLANATION")


def test_substantive_explanation_is_not_flagged_as_thin():
    card = make_card(
        front="What is osmosis?",
        back="diffusion of water",
        extra="Explanation: Solvent moves across a semipermeable membrane toward higher solute. Context: Topic: Bio.",
    )

    assert "THIN_EXPLANATION" not in {violation.code for violation in validate_card(card)}


def test_generic_fallback_prompt_is_flagged():
    card = make_card(
        front="What claim or evidence is presented in Ethics?",
        back="a specific claim",
        extra="Explanation: The source presents a moral claim about autonomy. Context: Topic: Ethics.",
    )

    assert "GENERIC_PROMPT" in {violation.code for violation in validate_card(card)}


def test_prose_that_only_renders_generically_is_deferred_not_faked(tmp_path):
    source = tmp_path / "ethics.md"
    output = tmp_path / "ethics.csv"
    source.write_text("# Ethics\nThe author argues for moral restraint.\n", encoding="utf-8")

    assert main([str(source), "--output", str(output), "--allow-violations"]) == 0

    with output.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == []  # no generic card was fabricated

    manifest = json.loads(output.with_suffix(".manifest.json").read_text())
    assert manifest["knowledge_units"]
    assert all(unit["status"] == "deferred" for unit in manifest["knowledge_units"])


def test_image_html_attributes_are_escaped():
    cards = build_cards(
        parse_content(
            '[image: a.png?x=1&y=2 | alt: The diagram cues spatial recall of the "labeled" parts.]\n'
            "Mitochondria produce energy."
        )
    )
    card = next(card for card in cards if card.image_url)

    assert "a.png?x=1&amp;y=2" in card.back
    assert "&quot;labeled&quot;" in card.back
