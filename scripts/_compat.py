"""Helpers shared by legacy compatibility wrappers."""

from pathlib import Path
import sys


def ensure_src_on_path() -> None:
    """Make the package importable directly from a source checkout."""
    source_path = str(Path(__file__).resolve().parents[1] / "src")
    if source_path not in sys.path:
        sys.path = [source_path, *sys.path]
