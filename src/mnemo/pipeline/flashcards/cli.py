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

from .authoring import (
    AiAuthoringError,
    CommandAiProvider,
    DeterministicAuthor,
    FileAiProvider,
    JsonAiAuthor,
)
from .io import analyze_retention, write_csv, write_json
from .models import GenerationConfig
from .parse import parse_content, plan_knowledge
from .policy import (
    CANDIDATE_CARDS_SECTION,
    DEFAULT_EASE_PERCENT,
    DEFAULT_EASY_INTERVAL_DAYS,
    DEFAULT_GENERATION_SEED,
    DEFAULT_GRADUATING_INTERVAL_DAYS,
    DEFAULT_LEARNING_STEPS,
    DEFAULT_NEW_CARDS_PER_DAY,
    DEFAULT_SCHEDULER,
)
from .render import interleave_cards
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
    parser.add_argument("--learning-steps", type=parse_steps, default=DEFAULT_LEARNING_STEPS)
    parser.add_argument("--graduating-interval", type=int, default=DEFAULT_GRADUATING_INTERVAL_DAYS)
    parser.add_argument("--easy-interval", type=int, default=DEFAULT_EASY_INTERVAL_DAYS)
    parser.add_argument("--starting-ease", type=int, default=DEFAULT_EASE_PERCENT)
    parser.add_argument("--max-ease", type=int, default=DEFAULT_EASE_PERCENT)
    parser.add_argument("--new-cards-per-day", type=int, default=DEFAULT_NEW_CARDS_PER_DAY)
    parser.add_argument("--scheduler", choices=("legacy-sm2", "fsrs"), default=DEFAULT_SCHEDULER)
    parser.add_argument(
        "--interleave",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Interleave cards across topics.",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_GENERATION_SEED)
    parser.add_argument("--author", choices=("deterministic", "ai"), default="deterministic")
    parser.add_argument("--ai-response-file", type=Path, help="Read JSON card drafts from a file.")
    parser.add_argument("--ai-command", help="Command that reads the AI prompt on stdin and writes JSON to stdout.")
    parser.add_argument("--retention-log", type=Path, help="Optional review CSV for the >21-day retention hook.")
    parser.add_argument(
        "--section",
        help=(
            "Generate only from a Markdown heading section. "
            f"Cornell notes default to {CANDIDATE_CARDS_SECTION!r} when present."
        ),
    )
    parser.add_argument("--allow-violations", action="store_true", help="Exit zero even when rubric errors remain.")
    return parser


def selected_source_text(source_text: str, input_path: Path, section: str | None) -> str:
    requested = section
    if requested is None and input_path.name.endswith(".cornell.md"):
        requested = CANDIDATE_CARDS_SECTION
    if requested is None:
        return source_text
    extracted = extract_markdown_section(source_text, requested)
    if extracted is None:
        raise ValueError(f"Markdown section not found: {requested}")
    return extracted


def extract_markdown_section(source_text: str, heading: str) -> str | None:
    target = heading.strip().casefold()
    lines = source_text.splitlines()
    start: int | None = None
    level = 0
    for index, line in enumerate(lines):
        match = re.match(r"^(?P<marks>#{1,6})\s+(?P<title>.+?)\s*$", line)
        if not match:
            continue
        current_level = len(match.group("marks"))
        title = match.group("title").strip().casefold()
        if start is None and title == target:
            start = index
            level = current_level
            continue
        if start is not None and current_level <= level:
            return "\n".join(lines[start:index]).strip() + "\n"
    if start is None:
        return None
    return "\n".join(lines[start:]).strip() + "\n"


def build_author(args: argparse.Namespace) -> DeterministicAuthor | JsonAiAuthor:
    providers = [bool(args.ai_response_file), bool(args.ai_command)]
    if args.author == "deterministic":
        if any(providers):
            raise AiAuthoringError("AI providers require --author ai.")
        return DeterministicAuthor()
    if sum(providers) != 1:
        raise AiAuthoringError("AI authoring requires exactly one of --ai-response-file or --ai-command.")
    provider = (
        FileAiProvider(args.ai_response_file)
        if args.ai_response_file
        else CommandAiProvider(args.ai_command)
    )
    return JsonAiAuthor(provider)


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
    try:
        source_text = args.input.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"Could not read input: {exc}", file=sys.stderr)
        return 2
    try:
        generation_text = selected_source_text(source_text, args.input, args.section)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    units = parse_content(generation_text, args.input.name)
    objectives, knowledge_units = plan_knowledge(units, generation_text, args.input.name)
    try:
        cards = build_author(args).author(units)
    except AiAuthoringError as exc:
        print(f"AI authoring failed: {exc}", file=sys.stderr)
        return 2
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
    return 0 if args.allow_violations or (errors == 0 and deferred == 0) else 2
