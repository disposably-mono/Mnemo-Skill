"""Refresh fingerprints in generated Mnemo sidecars."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mnemo.pipeline.flashcards.io import regenerate_sidecar_fingerprints


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="Generated card CSV.")
    args = parser.parse_args(argv)
    try:
        updated = regenerate_sidecar_fingerprints(args.csv)
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"Sidecar regeneration failed: {exc}", file=sys.stderr)
        return 1
    print(f"Updated {len(updated)} sidecar(s) for {args.csv}")
    return 0
