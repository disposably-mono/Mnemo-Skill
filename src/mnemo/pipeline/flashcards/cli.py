"""Generate rubric-audited, Anki-compatible flashcards from study notes.

The generator is deliberately deterministic and conservative. It can recognize
common note structures and split obvious compound facts, but it reports
ambiguous cases for human review instead of pretending heuristic NLP is exact.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from mnemo.core.knowledge import build_coverage_report

from .io import analyze_retention, write_csv, write_json
from .models import DEFAULT_SEED, GenerationConfig
from .parse import parse_content, plan_knowledge
from .render import build_cards, interleave_cards
from .validate import validate_deck

def parse_steps(value: str) -> tuple[str, ...]:
    steps = tuple(part for part in re.split(r"[,\s]+", value.strip()) if part)
    if not steps or not all(re.fullmatch(r"\d+[mhd]", step.lower()) for step in steps):
        raise argparse.ArgumentTypeError("steps must look like '10m 1d' or '10m,1d'")
    return steps


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Text or Markdown source file.")
    parser.add_argument("--output", type=Path, required=True, help="Output Anki-compatible CSV.")
    parser.add_argument("--learning-steps", type=parse_steps, default=("10m", "1d"))
    parser.add_argument("--graduating-interval", type=int, default=3)
    parser.add_argument("--easy-interval", type=int, default=7)
    parser.add_argument("--starting-ease", type=int, default=250)
    parser.add_argument("--max-ease", type=int, default=250)
    parser.add_argument("--new-cards-per-day", type=int, default=20)
    parser.add_argument("--scheduler", choices=("legacy-sm2", "fsrs"), default="legacy-sm2")
    parser.add_argument(
        "--interleave",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Interleave cards across topics.",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--retention-log", type=Path, help="Optional review CSV for the >21-day retention hook.")
    parser.add_argument("--allow-violations", action="store_true", help="Exit zero even when rubric errors remain.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.input.exists():
        print(f"Input does not exist: {args.input}", file=sys.stderr)
        return 2
    config = GenerationConfig(
        learning_steps=args.learning_steps,
        graduating_interval_days=args.graduating_interval,
        easy_interval_days=args.easy_interval,
        starting_ease_percent=args.starting_ease,
        max_ease_percent=args.max_ease,
        new_cards_per_day=args.new_cards_per_day,
        scheduler=args.scheduler,
        interleave_topics=args.interleave,
        seed=args.seed,
    )
    source_text = args.input.read_text(encoding="utf-8")
    units = parse_content(source_text, args.input.name)
    objectives, knowledge_units = plan_knowledge(units, source_text, args.input.name)
    cards = build_cards(units)
    if config.interleave_topics:
        cards = interleave_cards(cards, config.seed)
    violations = validate_deck(cards, config)

    write_csv(cards, args.output)
    settings_path = args.output.with_suffix(".settings.json")
    violations_path = args.output.with_suffix(".violations.json")
    retention_path = args.output.with_suffix(".retention.json")
    manifest_path = args.output.with_suffix(".manifest.json")
    coverage_path = args.output.with_suffix(".coverage.json")
    represented = {card.knowledge_unit_id for card in cards if card.knowledge_unit_id}
    for unit in knowledge_units:
        if unit.id not in represented:
            unit.status = "deferred"
    settings = {
        **asdict(config),
        "learning_steps": list(config.learning_steps),
        "portable_easy_button_enforcement": False,
        "note": "CSV import cannot disable Anki's Easy button; 'avoid' is a review policy.",
    }
    write_json(settings, settings_path)
    write_json([asdict(violation) for violation in violations], violations_path)
    write_json(analyze_retention(args.retention_log) if args.retention_log else {"status": "not-provided", "mature_reviews": 0, "rows": []}, retention_path)
    write_json(
        {
            "version": 1,
            "source": args.input.name,
            "objectives": [objective.to_dict() for objective in objectives],
            "knowledge_units": [unit.to_dict() for unit in knowledge_units],
        },
        manifest_path,
    )
    coverage_report = build_coverage_report(objectives, knowledge_units)
    write_json(coverage_report, coverage_path)

    errors = sum(violation.level == "error" for violation in violations)
    warnings = sum(violation.level == "warning" for violation in violations)
    deferred = sum(unit.status == "deferred" for unit in knowledge_units)
    coverage_summary = coverage_report["summary"]
    print(f"Generated {len(cards)} cards; deferred {deferred} unit(s): {args.output}")
    if deferred:
        print(
            f"Author the {deferred} deferred unit(s) listed in {manifest_path} "
            "(status=deferred); the deterministic path only renders units it can "
            "ground specifically."
        )
    print(
        "Objectives: "
        f"{coverage_summary['covered_objectives']}/{coverage_summary['objectives']} covered"
    )
    print(f"Rubric: {errors} error(s), {warnings} warning(s): {violations_path}")
    print(f"Manifest: {manifest_path}")
    print(f"Coverage: {coverage_path}")
    print(f"Settings: {settings_path}")
    return 0 if args.allow_violations or errors == 0 else 2
