"""One-command readiness gate for audited Mnemo card CSV files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from mnemo.pipeline.audit_cards import build_report, print_report
from mnemo.pipeline.import_refined_csv import load_notes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="Mnemo refined card CSV.")
    parser.add_argument("--deck", required=True, help="Deck name used to validate Anki note conversion.")
    parser.add_argument("--settings", type=Path, help="Optional settings sidecar.")
    parser.add_argument("--coverage", type=Path, help="Optional objective coverage sidecar.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = args.settings or args.csv.with_suffix(".settings.json")
    coverage = args.coverage or args.csv.with_suffix(".coverage.json")
    try:
        report = build_report(args.csv, settings, coverage_path=coverage)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Readiness validation failed: {exc}", file=sys.stderr)
        return 2
    print_report(report)
    if report["status"] != "PASS":
        return 2
    try:
        deferred = deferred_manifest_units(args.csv.with_suffix(".manifest.json"))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Manifest validation failed: {exc}", file=sys.stderr)
        return 2
    if deferred:
        print(f"Manifest validation failed: {deferred} deferred unit(s) remain", file=sys.stderr)
        return 2
    try:
        notes, media = load_notes(args.csv, args.deck)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Import validation failed: {exc}", file=sys.stderr)
        return 2
    print(f"[PASS] Import Validation: {len(notes)} note(s), {len(media)} media file(s)")
    return 0


def deferred_manifest_units(path: Path) -> int:
    if not path.exists():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    units = data.get("knowledge_units", [])
    if not isinstance(units, list):
        raise ValueError("manifest knowledge_units must be a list")
    return sum(unit.get("status") == "deferred" for unit in units if isinstance(unit, dict))
