"""Bundled and note-specific media helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FONT_DIR = _REPO_ROOT / "assets" / "fonts"
_FONT_NAMES = (
    "_dmserifdisplay-regular.ttf",
    "_dmmono-regular.ttf",
    "_dmmono-medium.ttf",
    "_outfit-variable.ttf",
)


def bundled_font_paths() -> list[Path]:
    """Return the fonts referenced by the MONO note-type CSS."""
    paths = [_FONT_DIR / name for name in _FONT_NAMES]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing bundled fonts: {', '.join(missing)}")
    return paths


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
