"""Sidecar and CSV IO helpers for flashcard generation."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Sequence

from .models import CSV_FIELDS, Card


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file without loading it all at once."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def regenerate_sidecar_fingerprints(csv_path: Path) -> tuple[Path, ...]:
    """Refresh manifest/coverage CSV fingerprints atomically beside ``csv_path``."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)
    fingerprint = sha256_file(csv_path)
    updated: list[Path] = []
    for sidecar in (csv_path.with_suffix(".manifest.json"), csv_path.with_suffix(".coverage.json")):
        if not sidecar.exists():
            continue
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"sidecar must contain a JSON object: {sidecar}")
        fingerprints = data.get("fingerprints")
        if not isinstance(fingerprints, dict):
            fingerprints = {}
        data["fingerprints"] = {**fingerprints, "csv_sha256": fingerprint}
        payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        fd, temp_name = tempfile.mkstemp(prefix=f".{sidecar.name}.", dir=sidecar.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, sidecar)
        except BaseException:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise
        updated.append(sidecar)
    return tuple(updated)

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
