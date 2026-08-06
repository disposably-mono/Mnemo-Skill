"""Bundled and note-specific media helpers."""

from __future__ import annotations

from contextlib import ExitStack
from importlib import resources
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory
from typing import Iterable


_RESOURCE_FILES = ExitStack()
_EXTRACTED_RESOURCE_DIRECTORY = Path(
    _RESOURCE_FILES.enter_context(TemporaryDirectory(prefix="mnemo-fonts-"))
)


def bundled_font_paths() -> list[Path]:
    """Return real paths for the fonts referenced by the MONO note-type CSS.

    Resource files extracted from a zip distribution remain available until
    process exit so Anki backends can consume the returned paths.
    """
    font_root = resources.files("mnemo.resources.fonts")
    return sorted(
        _extracted_font_path(path)
        for path in font_root.iterdir()
        if path.name.endswith(".ttf")
    )


def _extracted_font_path(resource: resources.abc.Traversable) -> Path:
    """Materialize one font with the filename Anki's CSS references."""
    output_path = _EXTRACTED_RESOURCE_DIRECTORY / resource.name
    if output_path.exists():
        return output_path
    with resources.as_file(resource) as source_path:
        copyfile(source_path, output_path)
    return output_path


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
