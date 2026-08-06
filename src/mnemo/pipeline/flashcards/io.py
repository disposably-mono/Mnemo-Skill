"""Sidecar and CSV IO helpers for flashcard generation."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Sequence

from .models import CSV_FIELDS, Card

def write_csv(cards: Sequence[Card], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(card.to_row() for card in cards)


def write_json(data: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def analyze_retention(path: Path) -> dict[str, object]:
    """Compare predicted and actual recall for review rows with interval >21d."""
    mature: list[dict[str, object]] = []
    if not path.exists():
        return {"status": "not-provided", "mature_reviews": 0, "rows": []}
    with path.open(encoding="utf-8", newline="") as handle:
        for line_number, row in enumerate(csv.DictReader(handle), start=2):
            try:
                interval = float(row.get("interval_days", ""))
                predicted = float(row.get("predicted_retention", ""))
                actual = float(row.get("actual_recalled", ""))
            except (TypeError, ValueError):
                mature.append({"line": line_number, "error": "invalid numeric retention row"})
                continue
            if interval <= 21:
                continue
            mature.append(
                {
                    "card_id": row.get("card_id", ""),
                    "interval_days": interval,
                    "predicted_retention": predicted,
                    "actual_recalled": actual,
                    "calibration_error": round(actual - predicted, 4),
                }
            )
    valid = [row for row in mature if "calibration_error" in row]
    mean_error = (
        round(sum(float(row["calibration_error"]) for row in valid) / len(valid), 4)
        if valid
        else None
    )
    return {"status": "ok", "mature_reviews": len(valid), "mean_calibration_error": mean_error, "rows": mature}
