"""Bundled and note-specific media helpers."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Iterable


def bundled_font_paths() -> list[Path]:
    """Return the fonts referenced by the MONO note-type CSS."""
    font_root = resources.files("mnemo.resources.fonts")
    return sorted(
        Path(str(path))
        for path in font_root.iterdir()
        if path.name.endswith(".ttf")
    )


def unique_media_paths(paths: Iterable[Path]) -> list[Path]:
    """Deduplicate media by filename and reject ambiguous name collisions."""
    by_name: dict[str, Path] = {}
    for raw_path in paths:
        path = Path(raw_path)
        existing = by_name.get(path.name)
        if existing is None:
            by_name[path.name] = path
        elif existing.resolve() != path.resolve():
            raise ValueError(
                f"multiple media files use the filename {path.name!r}: "
                f"{existing} and {path}"
            )
    return list(by_name.values())
