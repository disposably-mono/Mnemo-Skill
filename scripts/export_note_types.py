"""Compatibility wrapper for the packaged note-type export command."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mnemo.pipeline.export_note_types import export_note_types, main

__all__ = ["export_note_types", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
