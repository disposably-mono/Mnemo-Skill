import json
import sys

import pytest

from mnemo.pipeline.generate_flashcards import (
    AiAuthoringError,
    CommandAiProvider,
    FileAiProvider,
    JsonAiAuthor,
    build_authoring_prompt,
    parse_content,
    plan_knowledge,
    validate_card,
)


def planned_units(text, source_name):
    units = parse_content(text, source_name)
    plan_knowledge(units, text, source_name)
    return units


def test_json_ai_author_converts_structured_cards(tmp_path):
    response = tmp_path / "cards.json"
    units = planned_units("ATP synthase uses a proton gradient.", "bio.md")
    response.write_text(
        json.dumps(
            {
                "cards": [
                    {
                        "front": "What does ATP synthase use?",
                        "back": "A proton gradient.",
                        "extra": (
                            "Explanation: The source states ATP synthase uses a proton gradient. "
                            "Context: ATP synthase is an enzyme in cellular energy conversion."
                        ),
                        "card_type": "qa",
                        "tags": ["bio"],
                        "source_unit_id": units[0].knowledge_unit_id,
                        "evidence": "ATP synthase uses a proton gradient.",
                        "confidence": 0.88,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    cards = JsonAiAuthor(FileAiProvider(response)).author(units)

    assert len(cards) == 1
    assert cards[0].front == "What does ATP synthase use?"
    assert cards[0].back == "A proton gradient."
    assert cards[0].card_type == "qa"
    assert cards[0].source == "bio.md:line-1"
    assert cards[0].knowledge_unit_id == units[0].knowledge_unit_id
    assert cards[0].confidence == 0.88
    assert not [violation for violation in validate_card(cards[0]) if violation.level == "error"]


def test_json_ai_author_rejects_malformed_json(tmp_path):
    response = tmp_path / "cards.json"
    response.write_text("not json", encoding="utf-8")
    units = planned_units("Water is H2O.", "chem.md")

    with pytest.raises(AiAuthoringError, match="valid JSON"):
        JsonAiAuthor(FileAiProvider(response)).author(units)


def test_json_ai_author_rejects_missing_required_card_fields(tmp_path):
    response = tmp_path / "cards.json"
    response.write_text(json.dumps({"cards": [{"front": "Question?"}]}), encoding="utf-8")
    units = planned_units("Water is H2O.", "chem.md")

    with pytest.raises(AiAuthoringError, match="missing required"):
        JsonAiAuthor(FileAiProvider(response)).author(units)


def test_json_ai_author_matches_cards_by_source_unit_id(tmp_path):
    response = tmp_path / "cards.json"
    units = planned_units("Water is H2O.\nSodium chloride is table salt.", "chem.md")
    response.write_text(
        json.dumps(
            {
                "cards": [
                    {
                        "source_unit_id": units[1].knowledge_unit_id,
                        "front": "What is sodium chloride?",
                        "back": "Table salt.",
                        "extra": "Explanation: The source equates sodium chloride with table salt.",
                        "card_type": "qa",
                        "evidence": "Sodium chloride is table salt.",
                    },
                    {
                        "source_unit_id": units[0].knowledge_unit_id,
                        "front": "What is water?",
                        "back": "H2O.",
                        "extra": "Explanation: The source gives H2O as water's formula.",
                        "card_type": "qa",
                        "evidence": "Water is H2O.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    cards = JsonAiAuthor(FileAiProvider(response)).author(units)

    assert [card.knowledge_unit_id for card in cards] == [
        units[1].knowledge_unit_id,
        units[0].knowledge_unit_id,
    ]
    assert [card.source for card in cards] == ["chem.md:line-2", "chem.md:line-1"]


def test_json_ai_author_allows_multiple_cards_for_one_source_unit(tmp_path):
    response = tmp_path / "cards.json"
    units = planned_units("Water is H2O.", "chem.md")
    response.write_text(
        json.dumps(
            {
                "cards": [
                    {
                        "source_unit_id": units[0].knowledge_unit_id,
                        "front": "What is water?",
                        "back": "H2O.",
                        "extra": "Explanation: The source states water is H2O.",
                        "card_type": "qa",
                        "evidence": "Water is H2O.",
                    },
                    {
                        "source_unit_id": units[0].knowledge_unit_id,
                        "front": "What formula does the source give for water?",
                        "back": "H2O.",
                        "extra": "Explanation: The same source sentence gives water's formula.",
                        "card_type": "qa",
                        "evidence": "Water is H2O.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    cards = JsonAiAuthor(FileAiProvider(response)).author(units)

    assert len(cards) == 2
    assert {card.knowledge_unit_id for card in cards} == {units[0].knowledge_unit_id}


def test_json_ai_author_rejects_unmatched_or_unsupported_drafts(tmp_path):
    response = tmp_path / "cards.json"
    units = planned_units("Water is H2O.", "chem.md")
    response.write_text(
        json.dumps(
            {
                "cards": [
                    {
                        "source_unit_id": units[0].knowledge_unit_id,
                        "front": "What does ATP synthase use?",
                        "back": "A proton gradient.",
                        "extra": "Explanation: The source states ATP synthase uses a proton gradient.",
                        "card_type": "qa",
                        "evidence": "ATP synthase uses a proton gradient.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(AiAuthoringError, match="evidence"):
        JsonAiAuthor(FileAiProvider(response)).author(units)


def test_json_ai_author_rejects_unknown_source_unit_id(tmp_path):
    response = tmp_path / "cards.json"
    units = planned_units("Water is H2O.", "chem.md")
    response.write_text(
        json.dumps(
            {
                "cards": [
                    {
                        "source_unit_id": "unit-missing",
                        "front": "What is water?",
                        "back": "H2O.",
                        "extra": "Explanation: The source states water is H2O.",
                        "card_type": "qa",
                        "evidence": "Water is H2O.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(AiAuthoringError, match="unknown source_unit_id"):
        JsonAiAuthor(FileAiProvider(response)).author(units)


def test_command_ai_provider_sends_prompt_on_stdin(tmp_path):
    script = tmp_path / "fake_ai.py"
    script.write_text(
        "import json, sys\n"
        "prompt = sys.stdin.read()\n"
        "assert 'source_units' in prompt\n"
        "print(json.dumps({'cards': []}))\n",
        encoding="utf-8",
    )

    output = CommandAiProvider(f"{sys.executable} {script}").complete(
        build_authoring_prompt(planned_units("Water is H2O.", "chem.md"))
    )

    assert json.loads(output) == {"cards": []}
