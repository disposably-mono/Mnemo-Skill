#!/usr/bin/env python3
"""Audit a generated flashcard CSV against Mnemo's card-quality rubric."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.generate_flashcards import (  # noqa: E402
    Card,
    GenerationConfig,
    Violation,
    analyze_retention,
    validate_deck,
    word_count,
)


REQUIRED_FIELDS = ("Front", "Back", "Extra", "Mnemonic", "CardType", "Tags")


def load_cards(path: Path) -> tuple[list[Card], list[Violation]]:
    cards: list[Card] = []
    violations: list[Violation] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in REQUIRED_FIELDS if field not in (reader.fieldnames or [])]
        if missing:
            violations.append(
                Violation(
                    "error",
                    "CSV_FIELDS",
                    f"CSV is missing required fields: {', '.join(missing)}.",
                    action="Regenerate with the Mnemo CSV schema.",
                )
            )
            return cards, violations
        for line_number, row in enumerate(reader, start=2):
            try:
                cards.append(
                    Card(
                        front=(row.get("Front") or "").strip(),
                        back=(row.get("Back") or "").strip(),
                        extra=(row.get("Extra") or "").strip(),
                        mnemonic=(row.get("Mnemonic") or "").strip(),
                        card_type=(row.get("CardType") or "").strip(),
                        tags=(row.get("Tags") or "").split(),
                        image_url=(row.get("ImageURL") or "").strip(),
                        image_alt=(row.get("ImageAlt") or "").strip(),
                        topic=(row.get("Topic") or "General").strip(),
                        source=(row.get("Source") or f"{path.name}:line-{line_number}").strip(),
                        card_id=(row.get("CardID") or f"line-{line_number}").strip(),
                    )
                )
            except (AttributeError, TypeError) as exc:
                violations.append(
                    Violation(
                        "error",
                        "CSV_ROW",
                        f"Line {line_number} could not be parsed: {exc}.",
                        action="Repair the malformed CSV row.",
                    )
                )
    return cards, violations


def load_config(path: Path | None) -> tuple[GenerationConfig, list[Violation]]:
    if path is None or not path.exists():
        return GenerationConfig(), [
            Violation(
                "warning",
                "SETTINGS_MISSING",
                "No settings sidecar was found; requested Anki defaults were assumed.",
                action="Pass --settings deck.settings.json to verify scheduler settings.",
            )
        ]
    data = json.loads(path.read_text(encoding="utf-8"))
    try:
        return GenerationConfig(
            learning_steps=tuple(data.get("learning_steps", ("10m", "1d"))),
            graduating_interval_days=int(data.get("graduating_interval_days", 3)),
            easy_interval_days=int(data.get("easy_interval_days", 7)),
            starting_ease_percent=int(data.get("starting_ease_percent", 250)),
            max_ease_percent=int(data.get("max_ease_percent", 250)),
            new_cards_per_day=int(data.get("new_cards_per_day", 20)),
            scheduler=str(data.get("scheduler", "legacy-sm2")),
            easy_button_policy=str(data.get("easy_button_policy", "avoid")),
            interleave_topics=bool(data.get("interleave_topics", True)),
            seed=int(data.get("seed", 42)),
        ), []
    except (TypeError, ValueError) as exc:
        return GenerationConfig(), [
            Violation(
                "error",
                "SETTINGS_INVALID",
                f"Settings sidecar is invalid: {exc}.",
                action="Regenerate the settings sidecar.",
            )
        ]


def duplicate_violations(cards: Sequence[Card]) -> list[Violation]:
    signatures: Counter[tuple[str, str]] = Counter(
        (card.front.casefold(), card.back.casefold()) for card in cards
    )
    return [
        Violation(
            "warning",
            "DUPLICATE_CARD",
            f"The same Front/Back pair appears {count} times.",
            action="Delete duplicate notes unless repetition is intentional.",
        )
        for count in signatures.values()
        if count > 1
    ]


def build_report(
    csv_path: Path,
    settings_path: Path | None = None,
    retention_log: Path | None = None,
) -> dict[str, object]:
    cards, parse_violations = load_cards(csv_path)
    config, config_violations = load_config(settings_path)
    violations = [
        *parse_violations,
        *config_violations,
        *validate_deck(cards, config),
        *duplicate_violations(cards),
    ]
    errors = [violation for violation in violations if violation.level == "error"]
    warnings = [violation for violation in violations if violation.level == "warning"]
    type_counts = Counter(card.card_type for card in cards)
    long_fronts = sum(word_count(card.front) > 19 for card in cards)
    actions = list(dict.fromkeys(v.action for v in violations if v.action))
    return {
        "status": "PASS" if not errors else "FAIL",
        "deck": str(csv_path),
        "summary": {
            "cards": len(cards),
            "errors": len(errors),
            "warnings": len(warnings),
            "fronts_over_19_words": long_fronts,
            "card_types": dict(type_counts),
            "image_supported_cards": sum(bool(card.image_url) for card in cards),
            "topics": len({card.topic for card in cards}),
        },
        "checks": {
            "atomicity": not any(v.code in {"ATOMICITY_REVIEW", "COGNITIVE_LOAD"} for v in violations),
            "reading_time": long_fronts == 0,
            "format_variety": len(type_counts) >= 3,
            "pre_understanding": all(card.extra.startswith("Explanation:") for card in cards),
            "multimodal": any(card.image_url for card in cards),
            "daily_limit": config.new_cards_per_day <= 20,
            "ease_cap": config.max_ease_percent <= 250,
            "interleaving": not any(v.code == "INTERLEAVING" for v in violations),
        },
        "violations": [asdict(violation) for violation in violations],
        "iteration_actions": actions,
        "retention": analyze_retention(retention_log) if retention_log else {"status": "not-provided", "mature_reviews": 0, "rows": []},
    }


def print_report(report: dict[str, object]) -> None:
    summary = report["summary"]
    assert isinstance(summary, dict)
    print(f"{report['status']}: {report['deck']}")
    print(
        f"Cards: {summary['cards']} | Errors: {summary['errors']} | "
        f"Warnings: {summary['warnings']}"
    )
    print(f"Card types: {summary['card_types']}")
    checks = report["checks"]
    assert isinstance(checks, dict)
    for name, passed in checks.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name.replace('_', ' ').title()}")
    violations = report["violations"]
    assert isinstance(violations, list)
    for violation in violations:
        card = f" card={violation['card_id']}" if violation.get("card_id") else ""
        print(f"- {violation['level'].upper()} {violation['code']}{card}: {violation['message']}")
    actions = report["iteration_actions"]
    assert isinstance(actions, list)
    if actions:
        print("Iteration actions:")
        for action in actions:
            print(f"- {action}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", type=Path, help="Generated Mnemo CSV deck.")
    parser.add_argument("--settings", type=Path, help="Generator .settings.json sidecar.")
    parser.add_argument("--retention-log", type=Path, help="Review log CSV with predicted/actual retention.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.deck.exists():
        print(f"Deck does not exist: {args.deck}", file=sys.stderr)
        return 2
    settings = args.settings
    if settings is None:
        candidate = args.deck.with_suffix(".settings.json")
        settings = candidate if candidate.exists() else None
    report = build_report(args.deck, settings, args.retention_log)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_report(report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
