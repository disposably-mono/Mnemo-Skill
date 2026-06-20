#!/usr/bin/env python3
"""Build an auditable calibration report from approval and retention logs."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.generate_flashcards import analyze_retention  # noqa: E402


APPROVAL_FIELDS = ("card_id", "decision", "edited_fields", "reason")
DECISIONS = ("approved", "edited", "rejected")


def sorted_counts(counts: Counter[str]) -> dict[str, int]:
    """Return counts ordered by frequency, then key for deterministic ties."""
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def approval_metrics(path: Path) -> tuple[dict[str, object], dict[str, int], dict[str, int]]:
    """Read an approval log and calculate first-pass and review aggregates."""
    decisions: Counter[str] = Counter()
    rejection_reasons: Counter[str] = Counter()
    edit_hotspots: Counter[str] = Counter()
    invalid_rows = 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        valid_schema = all(field in (reader.fieldnames or []) for field in APPROVAL_FIELDS)
        for row in reader:
            decision = (row.get("decision") or "").strip().casefold()
            if not valid_schema or decision not in DECISIONS:
                invalid_rows += 1
                continue
            decisions[decision] += 1
            if decision == "rejected":
                rejection_reasons[(row.get("reason") or "").strip()] += 1
            if decision == "edited":
                fields = (row.get("edited_fields") or "").split(";")
                edit_hotspots.update(field.strip() for field in fields if field.strip())
    total = sum(decisions.values())
    rate = round(decisions["approved"] / total, 4) if total else None
    approval = {
        "total": total,
        "approved": decisions["approved"],
        "edited": decisions["edited"],
        "rejected": decisions["rejected"],
        "invalid_rows": invalid_rows,
        "first_pass_approval_rate": rate,
        "meets_90pct_target": rate >= 0.9 if rate is not None else None,
    }
    return approval, sorted_counts(rejection_reasons), sorted_counts(edit_hotspots)


def mature_rows(retention: dict[str, object]) -> list[dict[str, object]]:
    """Select valid mature rows already parsed by analyze_retention."""
    rows = retention.get("rows", [])
    if not isinstance(rows, list):
        return []
    return [
        row
        for row in rows
        if isinstance(row, dict)
        and "calibration_error" in row
        and "predicted_retention" in row
        and "actual_recalled" in row
    ]


def calibration_buckets(rows: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    """Group mature reviews into deterministic 0.1-wide prediction buckets."""
    groups: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for row in rows:
        predicted = float(row["predicted_retention"])
        actual = float(row["actual_recalled"])
        bucket = min(max(int(predicted * 10), 0), 9)
        groups[bucket].append((predicted, actual))
    buckets: list[dict[str, object]] = []
    for bucket, values in sorted(groups.items()):
        count = len(values)
        buckets.append(
            {
                "predicted_range": f"{bucket / 10:.1f}-{(bucket + 1) / 10:.1f}",
                "mean_predicted": round(sum(value[0] for value in values) / count, 4),
                "mean_actual": round(sum(value[1] for value in values) / count, 4),
                "n": count,
            }
        )
    return buckets


def retention_metrics(
    path: Path, retention: dict[str, object] | None = None
) -> dict[str, object]:
    """Extend the existing retention analysis with proper scoring metrics.

    Accepts an already-parsed ``retention`` dict so a caller that has run
    ``analyze_retention`` need not re-read and re-parse the same log file.
    """
    if retention is None:
        retention = analyze_retention(path)
    rows = mature_rows(retention)
    brier_score = None
    if rows:
        squared_errors = [
            (float(row["predicted_retention"]) - float(row["actual_recalled"])) ** 2
            for row in rows
        ]
        brier_score = round(sum(squared_errors) / len(squared_errors), 4)
    return {
        **retention,
        "brier_score": brier_score,
        "buckets": calibration_buckets(rows),
    }


def build_report(
    approval_log: Path | None = None,
    retention_log: Path | None = None,
    retention: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build a calibration report without inferring evidence that was not supplied.

    ``retention`` may be a pre-parsed ``analyze_retention`` result, letting a
    caller that already parsed the log avoid a second read of the same file.
    """
    approval: dict[str, object] = {"status": "not-provided"}
    rejection_reasons: dict[str, int] = {}
    edit_hotspots: dict[str, int] = {}
    # Guard existence here, symmetric with retention (analyze_retention checks
    # path.exists()): a missing approval log yields a not-provided block rather
    # than raising FileNotFoundError out of approval_metrics. The calibrate CLI
    # still rejects missing paths up front in main().
    if approval_log is not None and approval_log.exists():
        approval, rejection_reasons, edit_hotspots = approval_metrics(approval_log)
    retention = (
        retention_metrics(retention_log, retention)
        if retention_log is not None
        else {"status": "not-provided"}
    )
    return {
        "status": "ok",
        "approval": approval,
        "rejection_reasons": rejection_reasons,
        "edit_hotspots": edit_hotspots,
        "retention": retention,
    }


def print_report(report: dict[str, object]) -> None:
    """Print a concise human-readable calibration summary."""
    approval = report["approval"]
    retention = report["retention"]
    assert isinstance(approval, dict) and isinstance(retention, dict)
    # "ok" means the report ran, not that the data passed any threshold; invalid
    # approval rows and missing logs are reported on their own lines below.
    print("Calibration report:")
    if approval.get("status") == "not-provided":
        print("Approval: not provided")
    else:
        print(
            f"Approval: {approval['approved']}/{approval['total']} first-pass "
            f"(rate={approval['first_pass_approval_rate']}, invalid={approval['invalid_rows']})"
        )
    if retention.get("status") == "not-provided":
        print("Retention: not provided")
    else:
        print(
            f"Retention: {retention['mature_reviews']} mature reviews "
            f"(Brier={retention['brier_score']})"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval-log", type=Path, help="Approval decision CSV.")
    parser.add_argument("--retention-log", type=Path, help="Review retention CSV.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = (args.approval_log, args.retention_log)
    if not any(paths):
        print("At least one of --approval-log or --retention-log is required.", file=sys.stderr)
        return 2
    missing = next((path for path in paths if path is not None and not path.exists()), None)
    if missing is not None:
        print(f"Log does not exist: {missing}", file=sys.stderr)
        return 2
    report = build_report(args.approval_log, args.retention_log)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
