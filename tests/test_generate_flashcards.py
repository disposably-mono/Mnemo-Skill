import csv
import json
from collections import Counter

from mnemo.pipeline.generate_flashcards import (
    Card,
    GenerationConfig,
    analyze_retention,
    atomic_units,
    build_cards,
    choose_card_type,
    estimate_components,
    interleave_cards,
    looks_compound,
    main,
    parse_content,
    parse_steps,
    plan_knowledge,
    requires_context,
    split_list_items,
    split_sentences,
    validate_card,
    validate_deck,
    word_count,
)
from mnemo.pipeline.audit_cards import build_report
from mnemo.core.knowledge import extract_explicit_objectives


def _texts(units):
    return [unit.text for unit in units]


def test_you_can_prose_becomes_a_unit_instead_of_being_dropped():
    source = "You can compute variance as E[X^2] minus the square of E[X].\n"
    units = parse_content(source, "stats.md")
    assert any("variance" in text for text in _texts(units))
    assert not extract_explicit_objectives(source, "stats.md")


def test_students_can_declarative_content_is_not_an_objective():
    source = "Students can develop antibodies after infection.\n"
    units = parse_content(source, "bio.md")
    assert any("antibodies" in text for text in _texts(units))
    assert not extract_explicit_objectives(source, "bio.md")


def test_should_be_able_to_remains_an_objective_and_is_not_carded():
    source = "You should be able to derive the quadratic formula.\n"
    units = parse_content(source, "algebra.md")
    assert not any("quadratic" in text for text in _texts(units))
    objectives = extract_explicit_objectives(source, "algebra.md")
    assert len(objectives) == 1
    assert "derive the quadratic formula" in objectives[0].label


def test_bare_can_under_objectives_header_stays_an_objective():
    source = "Objectives:\nYou can identify the three phases of mitosis.\n"
    units = parse_content(source, "cell.md")
    assert not any("mitosis" in text for text in _texts(units))
    objectives = extract_explicit_objectives(source, "cell.md")
    assert len(objectives) == 1
    assert "identify the three phases of mitosis" in objectives[0].label


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


def test_numeric_answer_with_thousands_separators_is_not_split():
    units = parse_content(
        "Q: How many cells are estimated to die each day in an adult human?\n"
        "A: 300,000"
    )

    assert len(units) == 1
    assert units[0].answer == "300,000"
    cards = build_cards(units)
    assert len(cards) == 1
    assert "300,000" in cards[0].back
    assert "component" not in cards[0].front.lower()


def test_split_list_items_ignores_thousands_separator_commas():
    assert split_list_items("300,000") == []
    assert split_list_items("1,234,567,890,123") == []


def test_split_list_items_still_splits_genuine_enumerations():
    assert split_list_items("insulin, glucagon, and somatostatin") == [
        "insulin",
        "glucagon",
        "somatostatin",
    ]
    assert split_list_items("1, 2, 3") == ["1", "2", "3"]


def test_parse_steps_accepts_space_or_comma_separated_learning_steps():
    assert parse_steps("10m 1d") == ("10m", "1d")
    assert parse_steps("10m,1d") == ("10m", "1d")


def test_parse_content_preserves_fenced_code_as_one_verbatim_unit():
    source = """
```python
for i in range(3):
    print(i)
```
"""

    units = parse_content(source, "example.md")

    assert len(units) == 1
    assert units[0].text == "for i in range(3):\n    print(i)"
    assert units[0].verbatim_kind == "code"
    assert units[0].verbatim_language == "python"


def test_parse_content_preserves_display_math_as_one_verbatim_unit():
    units = parse_content("$$\nE = mc^2\n$$", "physics.md")

    assert len(units) == 1
    assert units[0].text == "$$\nE = mc^2\n$$"
    assert units[0].verbatim_kind == "math"


def test_parse_content_preserves_same_line_display_math_without_formula_classification():
    source = "$$ E = mc^2 $$"
    units = parse_content(source, "physics.md")
    _, knowledge = plan_knowledge(units, source, "physics.md")

    assert len(units) == 1
    assert units[0].text == source
    assert units[0].verbatim_kind == "math"
    assert knowledge[0].kind == "fact"


def test_parse_content_accepts_fence_language_after_whitespace():
    units = parse_content("``` python\nprint(1)\n```")

    assert len(units) == 1
    assert units[0].text == "print(1)"
    assert units[0].verbatim_language == "python"


def test_parse_content_keeps_unterminated_verbatim_blocks_opaque():
    code_units = parse_content("```python\nint x = 5;")
    math_units = parse_content("$$\nE = mc^2")

    assert [(unit.text, unit.verbatim_kind) for unit in code_units] == [
        ("int x = 5;", "code")
    ]
    assert [(unit.text, unit.verbatim_kind) for unit in math_units] == [
        ("$$\nE = mc^2", "math")
    ]


def test_verbatim_units_use_qa_instead_of_typed_cards():
    code_unit = parse_content("```python\nint x = 5;\n```")[0]
    math_unit = parse_content("$$ E = mc^2 $$")[0]

    assert choose_card_type(code_unit, 0, Counter()) == "qa"
    assert choose_card_type(math_unit, 0, Counter()) == "qa"
    assert build_cards([math_unit])[0].card_type == "qa"
    inline_math = parse_content("The derivative is \\frac{dy}{dx}.")[0]
    inline_math.knowledge_kind = "formula"
    assert choose_card_type(inline_math, 0, Counter()) == "qa"
    assert "mnemo-verbatim-code" in build_cards([code_unit])[0].tags


def test_inline_verbatim_spans_are_opaque_to_prose_splitting_and_counts():
    math = "The gradient \\(\\nabla f = (f_x, f_y)\\) points uphill."

    assert _texts(parse_content(math)) == [math]
    assert _texts(parse_content("Call `f(x, y)` to double.")) == [
        "Call `f(x, y)` to double."
    ]
    assert split_list_items("`f(x, y)`") == []
    assert estimate_components("\\(\\nabla f = (f_x, f_y)\\)") == 1
    assert word_count("The \\(\\nabla f = (f_x, f_y)\\) points uphill") == 3
    assert not looks_compound("\\(a; b and c\\)")


def test_validate_card_ignores_inline_verbatim_notation_and_literal_cloze_syntax():
    math_card = make_card(back="\\(\\nabla f = (f_x, f_y)\\)")
    literal_cloze_card = make_card(front="Use `{{c1::literal}}` as text.")

    assert not {"COGNITIVE_LOAD", "ATOMICITY_REVIEW"} & {
        violation.code for violation in validate_card(math_card)
    }
    assert "TYPE_FORMAT_MISMATCH" not in {
        violation.code for violation in validate_card(literal_cloze_card)
    }


def test_estimate_components_ignores_thousands_separator_commas():
    assert estimate_components("1,234,567,890,123") == 1


def test_real_three_item_list_still_splits_and_demands_mnemonic():
    units = parse_content("The primary colors include red, blue, and yellow.")

    assert [unit.answer for unit in units] == ["red", "blue", "yellow"]
    cards = build_cards(units)
    assert all(card.mnemonic for card in cards)

    card = make_card(back="insulin, glucagon, and somatostatin", mnemonic="")
    assert any(violation.code == "MISSING_MNEMONIC" for violation in validate_card(card))


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


def test_generated_card_text_fields_escape_html():
    card = build_cards(parse_content("Alpha is <script>alert(1)</script>."))[0]

    assert card.back == "&lt;script&gt;alert(1)&lt;/script&gt;"


def test_cli_with_no_interleave_produces_config_with_interleave_topics_false(tmp_path):
    source = tmp_path / "notes.md"
    output = tmp_path / "deck.csv"
    source.write_text(PASSING_NOTES, encoding="utf-8")

    assert main([str(source), "--output", str(output), "--no-interleave"]) == 0

    settings = json.loads(output.with_suffix(".settings.json").read_text())
    assert settings["interleave_topics"] is False


def test_cli_default_keeps_interleave_topics_true(tmp_path):
    source = tmp_path / "notes.md"
    output = tmp_path / "deck.csv"
    source.write_text(PASSING_NOTES, encoding="utf-8")

    assert main([str(source), "--output", str(output)]) == 0

    settings = json.loads(output.with_suffix(".settings.json").read_text())
    assert settings["interleave_topics"] is True


def test_cli_with_interleave_flag_explicitly_enables_interleave_topics(tmp_path):
    source = tmp_path / "notes.md"
    output = tmp_path / "deck.csv"
    source.write_text(PASSING_NOTES, encoding="utf-8")

    assert main([str(source), "--output", str(output), "--interleave"]) == 0

    settings = json.loads(output.with_suffix(".settings.json").read_text())
    assert settings["interleave_topics"] is True


def test_requires_context_ignores_plain_prose_but_flags_acronyms_and_keywords():
    assert requires_context("the cat sat") is False
    assert requires_context("DNA carries genetic information.") is True
    assert requires_context("This algorithm sorts the list.") is True


def test_declarative_definition_without_question_becomes_reverse_card():
    source = "Osmosis is the movement of water across a membrane."
    units = parse_content(source)
    plan_knowledge(units, source, "membrane.md")
    cards = build_cards(units)
    reverse_cards = [card for card in cards if card.card_type == "reverse"]

    assert len(reverse_cards) == 1
    assert reverse_cards[0].front == "Which term means: the movement of water across a membrane?"
    assert reverse_cards[0].back == "Osmosis"


def test_word_count_treats_accented_words_as_single_tokens():
    assert word_count("café") == 1
    assert word_count("naïve café") == 2
    assert word_count("well-known it's fine") == 3
