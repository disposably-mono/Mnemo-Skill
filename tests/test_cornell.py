import csv
import json
import sys

from mnemo.pipeline.generate_flashcards import main as generate_main, parse_content, plan_knowledge


def test_cornell_command_creates_contract_note_that_generates_cards(tmp_path):
    from mnemo.pipeline.cornell import main as cornell_main

    source = tmp_path / "source.md"
    note = tmp_path / "module.cornell.md"
    cards = tmp_path / "cards.csv"
    source.write_text(
        "# Living Systems\n"
        "Reductionism is analysis by breaking wholes into parts.\n"
        "Systems science says parts alone cannot explain living systems.\n",
        encoding="utf-8",
    )

    assert cornell_main(
        [
            str(source),
            "--output",
            str(note),
            "--course-slug",
            "science-11",
            "--module-slug",
            "01-perspective-on-living-systems",
            "--title",
            "Perspective on Living Systems",
            "--tag",
            "science-11",
        ]
    ) == 0

    text = note.read_text(encoding="utf-8")
    assert "## Source References" in text
    assert "## Cues" in text
    assert "## Notes" in text
    assert "## Summary" in text
    assert "## Follow-Up Gaps" in text
    assert "## Candidate Cards" in text
    assert "Q: What is Reductionism?" in text
    assert "A: analysis by breaking wholes into parts" in text
    assert "Tags: science-11" in text

    assert generate_main([str(note), "--output", str(cards)]) == 0
    with cards.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["Topic"] for row in rows} == {"Candidate Cards"}
    assert any(row["Front"] == "What is Reductionism?" for row in rows)


def test_cornell_command_fails_without_candidate_cards(tmp_path):
    from mnemo.pipeline.cornell import main as cornell_main

    source = tmp_path / "source.md"
    note = tmp_path / "module.cornell.md"
    source.write_text("A contextless fragment\n", encoding="utf-8")

    assert cornell_main([str(source), "--output", str(note)]) == 2
    assert not note.exists()


def test_cornell_command_rejects_frontmatter_control_characters(tmp_path):
    from mnemo.pipeline.cornell import main as cornell_main

    source = tmp_path / "source.md"
    note = tmp_path / "module.cornell.md"
    source.write_text("Reductionism is analysis by breaking wholes into parts.\n", encoding="utf-8")

    assert cornell_main(
        [
            str(source),
            "--output",
            str(note),
            "--course-slug",
            "science-11\nterm: hacked",
        ]
    ) == 2
    assert not note.exists()


def test_cornell_command_escapes_yaml_and_markdown_table_cells(tmp_path):
    from mnemo.pipeline.cornell import main as cornell_main

    source = tmp_path / "source.md"
    note = tmp_path / "module.cornell.md"
    source.write_text("Alpha is one | first.\n", encoding="utf-8")

    assert cornell_main(
        [
            str(source),
            "--output",
            str(note),
            "--course-slug",
            "science:11",
            "--tag",
            "alpha: beta",
        ]
    ) == 0
    text = note.read_text(encoding="utf-8")
    assert 'courseSlug: "science:11"' in text
    assert '  - "alpha: beta"' in text
    assert "one \\| first" in text


def test_cornell_command_skips_overpacked_candidates_instead_of_failing(tmp_path):
    from mnemo.pipeline.cornell import main as cornell_main

    source = tmp_path / "source.md"
    note = tmp_path / "module.cornell.md"
    cards = tmp_path / "cards.csv"
    source.write_text(
        "# Living Systems\n"
        "The extremely elaborate interpretive framework for understanding living systems "
        "in ancient, medieval, modern, ecological, molecular, and social biology is a model.\n"
        "Reductionism is analysis by breaking wholes into parts.\n",
        encoding="utf-8",
    )

    assert cornell_main([str(source), "--output", str(note)]) == 0

    text = note.read_text(encoding="utf-8")
    candidate_section = text.split("## Candidate Cards", 1)[1]
    assert "extremely elaborate interpretive framework" not in candidate_section
    assert "What is Reductionism?" in text
    assert generate_main([str(note), "--output", str(cards)]) == 0


def test_cornell_command_ai_response_file_creates_valid_note(tmp_path):
    from mnemo.pipeline.cornell import main as cornell_main

    source = tmp_path / "source.md"
    note = tmp_path / "module.cornell.md"
    cards = tmp_path / "cards.csv"
    source_text = "Reductionism is analysis by breaking wholes into parts.\n"
    units = parse_content(source_text, source.name)
    plan_knowledge(units, source_text, source.name)
    source.write_text(source_text, encoding="utf-8")
    response = tmp_path / "cornell.json"
    response.write_text(
        json.dumps(
            {
                "notes": [
                    {
                        "text": "Reductionism is analysis by breaking wholes into parts.",
                        "evidence": "Reductionism is analysis by breaking wholes into parts.",
                        "source_unit_id": units[0].knowledge_unit_id,
                    }
                ],
                "summary": {
                    "text": "Reductionism is analysis by breaking wholes into parts.",
                    "evidence": "Reductionism is analysis by breaking wholes into parts.",
                    "source_unit_id": units[0].knowledge_unit_id,
                },
                "follow_up_gaps": ["Confirm how the module contrasts systems science."],
                "candidate_cards": [
                    {
                        "source_unit_id": units[0].knowledge_unit_id,
                        "question": "What is reductionism?",
                        "answer": "Analysis by breaking wholes into parts.",
                        "extra": (
                            "Explanation: The source defines reductionism "
                            "through part-based analysis."
                        ),
                        "tags": ["science-11"],
                        "evidence": "Reductionism is analysis by breaking wholes into parts.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert cornell_main(
        [
            str(source),
            "--output",
            str(note),
            "--author",
            "ai",
            "--ai-response-file",
            str(response),
        ]
    ) == 0
    text = note.read_text(encoding="utf-8")
    assert "Reductionism is analysis by breaking wholes into parts." in text
    assert "Q: What is reductionism?" in text
    assert generate_main([str(note), "--output", str(cards)]) == 0


def test_cornell_command_ai_command_creates_valid_note(tmp_path):
    from mnemo.pipeline.cornell import main as cornell_main

    source = tmp_path / "source.md"
    note = tmp_path / "module.cornell.md"
    source.write_text(
        "Reductionism is analysis by breaking wholes into parts.\n",
        encoding="utf-8",
    )
    script = tmp_path / "author.py"
    script.write_text(
        """
import json
import sys

prompt = json.loads(sys.stdin.read())
unit = prompt["source_units"][0]
evidence = "Reductionism is analysis by breaking wholes into parts."
print(json.dumps({
    "notes": [{
        "text": evidence,
        "evidence": evidence,
        "source_unit_id": unit["source_unit_id"],
    }],
    "summary": {
        "text": evidence,
        "evidence": evidence,
        "source_unit_id": unit["source_unit_id"],
    },
    "follow_up_gaps": ["Confirm module-level contrast with systems science."],
    "candidate_cards": [{
        "source_unit_id": unit["source_unit_id"],
        "question": "What is reductionism?",
        "answer": "Analysis by breaking wholes into parts.",
        "extra": "Explanation: The source defines reductionism through part-based analysis.",
        "tags": ["science-11"],
        "evidence": evidence,
    }],
}))
""".strip(),
        encoding="utf-8",
    )

    assert cornell_main(
        [
            str(source),
            "--output",
            str(note),
            "--author",
            "ai",
            "--ai-command",
            f"{sys.executable} {script}",
        ]
    ) == 0
    text = note.read_text(encoding="utf-8")
    assert "Confirm module-level contrast with systems science." in text
    assert "Q: What is reductionism?" in text


def test_cornell_command_ai_response_rejects_unknown_source_unit_id(tmp_path):
    from mnemo.pipeline.cornell import main as cornell_main

    source = tmp_path / "source.md"
    note = tmp_path / "module.cornell.md"
    source.write_text("Water is H2O.\n", encoding="utf-8")
    response = tmp_path / "cornell.json"
    response.write_text(
        json.dumps(
            {
                "notes": [
                    {
                        "text": "Water is H2O.",
                        "evidence": "Water is H2O.",
                        "source_unit_id": "missing-unit",
                    }
                ],
                "summary": {
                    "text": "Water is H2O.",
                    "evidence": "Water is H2O.",
                    "source_unit_id": "missing-unit",
                },
                "candidate_cards": [
                    {
                        "source_unit_id": "missing-unit",
                        "question": "What is water?",
                        "answer": "H2O.",
                        "extra": "Explanation: The source states water is H2O.",
                        "evidence": "Water is H2O.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert cornell_main(
        [
            str(source),
            "--output",
            str(note),
            "--author",
            "ai",
            "--ai-response-file",
            str(response),
        ]
    ) == 2
    assert not note.exists()


def test_cornell_command_ai_response_rejects_unsupported_evidence(tmp_path):
    from mnemo.pipeline.cornell import main as cornell_main

    source = tmp_path / "source.md"
    note = tmp_path / "module.cornell.md"
    source_text = "Water is H2O.\n"
    units = parse_content(source_text, source.name)
    plan_knowledge(units, source_text, source.name)
    source.write_text(source_text, encoding="utf-8")
    response = tmp_path / "cornell.json"
    response.write_text(
        json.dumps(
            {
                "notes": [
                    {
                        "text": "Water is H2O.",
                        "evidence": "Water is H2O.",
                        "source_unit_id": units[0].knowledge_unit_id,
                    }
                ],
                "summary": {
                    "text": "Water is H2O.",
                    "evidence": "Water is H2O.",
                    "source_unit_id": units[0].knowledge_unit_id,
                },
                "candidate_cards": [
                    {
                        "source_unit_id": units[0].knowledge_unit_id,
                        "question": "What does ATP synthase use?",
                        "answer": "A proton gradient.",
                        "extra": (
                            "Explanation: The source states ATP synthase uses "
                            "a proton gradient."
                        ),
                        "evidence": "ATP synthase uses a proton gradient.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert cornell_main(
        [
            str(source),
            "--output",
            str(note),
            "--author",
            "ai",
            "--ai-response-file",
            str(response),
        ]
    ) == 2
    assert not note.exists()


def test_cornell_command_rejects_ai_provider_without_ai_author(tmp_path):
    from mnemo.pipeline.cornell import main as cornell_main

    source = tmp_path / "source.md"
    note = tmp_path / "module.cornell.md"
    response = tmp_path / "cornell.json"
    source.write_text("Reductionism is analysis by breaking wholes into parts.\n", encoding="utf-8")
    response.write_text("{}", encoding="utf-8")

    assert cornell_main([str(source), "--output", str(note), "--ai-response-file", str(response)]) == 2
    assert not note.exists()


def test_cornell_command_ai_response_rejects_candidate_injection(tmp_path):
    from mnemo.pipeline.cornell import main as cornell_main

    source = tmp_path / "source.md"
    note = tmp_path / "module.cornell.md"
    source_text = "Water is H2O.\n"
    units = parse_content(source_text, source.name)
    plan_knowledge(units, source_text, source.name)
    source.write_text(source_text, encoding="utf-8")
    response = tmp_path / "cornell.json"
    response.write_text(
        json.dumps(
            {
                "notes": [
                    {
                        "text": "Water is H2O.",
                        "evidence": "Water is H2O.",
                        "source_unit_id": units[0].knowledge_unit_id,
                    }
                ],
                "summary": {
                    "text": "Water is H2O.",
                    "evidence": "Water is H2O.",
                    "source_unit_id": units[0].knowledge_unit_id,
                },
                "candidate_cards": [
                    {
                        "source_unit_id": units[0].knowledge_unit_id,
                        "question": "What is water?",
                        "answer": "H2O.",
                        "extra": "Explanation: The source states water is H2O.",
                        "tags": ["chem\n\nQ: Injected?\nA: Bad"],
                        "evidence": "Water is H2O.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert cornell_main(
        [
            str(source),
            "--output",
            str(note),
            "--author",
            "ai",
            "--ai-response-file",
            str(response),
        ]
    ) == 2
    assert not note.exists()


def test_cornell_command_ai_response_rejects_non_list_tags(tmp_path):
    from mnemo.pipeline.cornell import main as cornell_main

    source = tmp_path / "source.md"
    note = tmp_path / "module.cornell.md"
    source_text = "Water is H2O.\n"
    units = parse_content(source_text, source.name)
    plan_knowledge(units, source_text, source.name)
    source.write_text(source_text, encoding="utf-8")
    response = tmp_path / "cornell.json"
    response.write_text(
        json.dumps(
            {
                "notes": [
                    {
                        "text": "Water is H2O.",
                        "evidence": "Water is H2O.",
                        "source_unit_id": units[0].knowledge_unit_id,
                    }
                ],
                "summary": {
                    "text": "Water is H2O.",
                    "evidence": "Water is H2O.",
                    "source_unit_id": units[0].knowledge_unit_id,
                },
                "candidate_cards": [
                    {
                        "source_unit_id": units[0].knowledge_unit_id,
                        "question": "What is water?",
                        "answer": "Water is H2O.",
                        "extra": "Explanation: The source states water is H2O.",
                        "tags": "science-11",
                        "evidence": "Water is H2O.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert cornell_main(
        [
            str(source),
            "--output",
            str(note),
            "--author",
            "ai",
            "--ai-response-file",
            str(response),
        ]
    ) == 2
    assert not note.exists()


def test_cornell_command_ai_response_rejects_answer_not_in_evidence(tmp_path):
    from mnemo.pipeline.cornell import main as cornell_main

    source = tmp_path / "source.md"
    note = tmp_path / "module.cornell.md"
    source_text = "Water is H2O.\n"
    units = parse_content(source_text, source.name)
    plan_knowledge(units, source_text, source.name)
    source.write_text(source_text, encoding="utf-8")
    response = tmp_path / "cornell.json"
    response.write_text(
        json.dumps(
            {
                "notes": [
                    {
                        "text": "Water is H2O.",
                        "evidence": "Water is H2O.",
                        "source_unit_id": units[0].knowledge_unit_id,
                    }
                ],
                "summary": {
                    "text": "Water is H2O.",
                    "evidence": "Water is H2O.",
                    "source_unit_id": units[0].knowledge_unit_id,
                },
                "candidate_cards": [
                    {
                        "source_unit_id": units[0].knowledge_unit_id,
                        "question": "What is water?",
                        "answer": "CO2.",
                        "extra": "Explanation: The source states water is CO2.",
                        "evidence": "Water is H2O.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert cornell_main(
        [
            str(source),
            "--output",
            str(note),
            "--author",
            "ai",
            "--ai-response-file",
            str(response),
        ]
    ) == 2
    assert not note.exists()


def test_cornell_command_ai_response_rejects_weak_substring_answer(tmp_path):
    from mnemo.pipeline.cornell import main as cornell_main

    source = tmp_path / "source.md"
    note = tmp_path / "module.cornell.md"
    source_text = "Water is H2O.\n"
    units = parse_content(source_text, source.name)
    plan_knowledge(units, source_text, source.name)
    source.write_text(source_text, encoding="utf-8")
    response = tmp_path / "cornell.json"
    response.write_text(
        json.dumps(
            {
                "notes": [
                    {
                        "text": "Water is H2O.",
                        "evidence": "Water is H2O.",
                        "source_unit_id": units[0].knowledge_unit_id,
                    }
                ],
                "summary": {
                    "text": "Water is H2O.",
                    "evidence": "Water is H2O.",
                    "source_unit_id": units[0].knowledge_unit_id,
                },
                "candidate_cards": [
                    {
                        "source_unit_id": units[0].knowledge_unit_id,
                        "question": "What is water?",
                        "answer": "is.",
                        "extra": "Explanation: The source states water is H2O.",
                        "evidence": "Water is H2O.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert cornell_main(
        [
            str(source),
            "--output",
            str(note),
            "--author",
            "ai",
            "--ai-response-file",
            str(response),
        ]
    ) == 2
    assert not note.exists()


def test_cornell_command_ai_response_rejects_unsupported_summary(tmp_path):
    from mnemo.pipeline.cornell import main as cornell_main

    source = tmp_path / "source.md"
    note = tmp_path / "module.cornell.md"
    source_text = "Water is H2O.\n"
    units = parse_content(source_text, source.name)
    plan_knowledge(units, source_text, source.name)
    source.write_text(source_text, encoding="utf-8")
    response = tmp_path / "cornell.json"
    response.write_text(
        json.dumps(
            {
                "notes": [
                    {
                        "text": "Water is H2O.",
                        "evidence": "Water is H2O.",
                        "source_unit_id": units[0].knowledge_unit_id,
                    }
                ],
                "summary": {
                    "text": "ATP synthase uses a proton gradient.",
                    "evidence": "Water is H2O.",
                    "source_unit_id": units[0].knowledge_unit_id,
                },
                "candidate_cards": [
                    {
                        "source_unit_id": units[0].knowledge_unit_id,
                        "question": "What is water?",
                        "answer": "H2O.",
                        "extra": "Explanation: The source states water is H2O.",
                        "evidence": "Water is H2O.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert cornell_main(
        [
            str(source),
            "--output",
            str(note),
            "--author",
            "ai",
            "--ai-response-file",
            str(response),
        ]
    ) == 2
    assert not note.exists()


def test_cornell_command_ai_response_rejects_summary_heading_injection(tmp_path):
    from mnemo.pipeline.cornell import main as cornell_main

    source = tmp_path / "source.md"
    note = tmp_path / "module.cornell.md"
    source_text = "Water is H2O and supports life.\n"
    units = parse_content(source_text, source.name)
    plan_knowledge(units, source_text, source.name)
    source.write_text(source_text, encoding="utf-8")
    response = tmp_path / "cornell.json"
    response.write_text(
        json.dumps(
            {
                "notes": [
                    {
                        "text": "Water is H2O and supports life.",
                        "evidence": "Water is H2O and supports life.",
                        "source_unit_id": units[0].knowledge_unit_id,
                    }
                ],
                "summary": {
                    "text": "Water is H2O and supports life. ## Candidate Cards",
                    "evidence": "Water is H2O and supports life.",
                    "source_unit_id": units[0].knowledge_unit_id,
                },
                "candidate_cards": [
                    {
                        "source_unit_id": units[0].knowledge_unit_id,
                        "question": "What is water?",
                        "answer": "Water is H2O.",
                        "extra": "Explanation: The source states water is H2O.",
                        "evidence": "Water is H2O and supports life.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert cornell_main(
        [
            str(source),
            "--output",
            str(note),
            "--author",
            "ai",
            "--ai-response-file",
            str(response),
        ]
    ) == 2
    assert not note.exists()
