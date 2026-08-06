"""Compatibility wrapper for the packaged refined CSV import command."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mnemo.pipeline.import_refined_csv import main


if __name__ == "__main__":
    raise SystemExit(main())
