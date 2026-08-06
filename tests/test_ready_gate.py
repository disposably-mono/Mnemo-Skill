import csv
import json

from mnemo.pipeline.generate_flashcards import main as generate_main


def test_ready_gate_passes_audited_csv_that_imports_to_anki_notes(tmp_path):
    from mnemo.pipeline.ready import main as ready_main

    source = tmp_path / "cards.md"
    output = tmp_path / "cards.csv"
    source.write_text(
        """\
## Candidate Cards

Q: What is osmosis?
A: Diffusion of water.
Extra: Solvent moves across a semipermeable membrane toward higher solute.
Tags: biology
""",
        encoding="utf-8",
    )
    assert generate_main([str(source), "--output", str(output)]) == 0

    assert ready_main([str(output), "--deck", "Mnemo::Science 11"]) == 0


def test_ready_gate_rejects_csv_that_audit_passes_but_cannot_import(tmp_path):
    from mnemo.pipeline.ready import main as ready_main

    csv_path = tmp_path / "bad.csv"
    settings_path = csv_path.with_suffix(".settings.json")
    coverage_path = csv_path.with_suffix(".coverage.json")
    violations_path = csv_path.with_suffix(".violations.json")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "Front",
                "Back",
                "Extra",
                "Mnemonic",
                "CardType",
                "Tags",
                "Topic",
                "Source",
                "CardID",
                "KnowledgeKind",
                "LearningPurpose",
                "Origin",
                "Confidence",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "Front": "What is alpha?",
                "Back": "The first letter.",
                "Extra": "Explanation: Alpha names the first position. Context: Topic: Greek.",
                "CardType": "unsupported",
                "Tags": "letters",
                "Topic": "Greek",
                "Source": "notes.md:line-1",
                "CardID": "bad-1",
                "KnowledgeKind": "fact",
                "LearningPurpose": "recall",
                "Origin": "source",
                "Confidence": "1.0",
            }
        )
    settings_path.write_text(
        json.dumps(
            {
                "learning_steps": ["10m", "1d"],
                "graduating_interval_days": 3,
                "easy_interval_days": 7,
                "starting_ease_percent": 250,
                "max_ease_percent": 250,
                "new_cards_per_day": 20,
                "scheduler": "legacy-sm2",
                "easy_button_policy": "avoid",
                "interleave_topics": True,
                "seed": 42,
            }
        ),
        encoding="utf-8",
    )
    coverage_path.write_text(
        json.dumps({"objectives": [], "summary": {"objectives": 0}}),
        encoding="utf-8",
    )
    violations_path.write_text("[]\n", encoding="utf-8")

    assert ready_main([str(csv_path), "--deck", "Mnemo::Science 11"]) == 2


def test_ready_gate_reports_missing_csv_without_traceback(tmp_path):
    from mnemo.pipeline.ready import main as ready_main

    missing = tmp_path / "missing.csv"

    assert ready_main([str(missing), "--deck", "Mnemo::Science 11"]) == 2


def test_ready_gate_rejects_deferred_manifest_units(tmp_path):
    from mnemo.pipeline.ready import main as ready_main

    source = tmp_path / "module.cornell.md"
    output = tmp_path / "module.cards.csv"
    source.write_text(
        """\
## Candidate Cards

Q: What is reductionist science?
A: Analysis by breaking wholes into parts.
Extra: The source describes reductionism as a mechanistic approach.

Q: What topics did the oversized source list include?
A: One, two, three, four, five, six, seven, eight, and nine.
Extra: The source lists too many items for one supported list card.
""",
        encoding="utf-8",
    )
    assert generate_main([str(source), "--output", str(output), "--allow-violations"]) == 0

    assert ready_main([str(output), "--deck", "Mnemo::Science 11"]) == 2
