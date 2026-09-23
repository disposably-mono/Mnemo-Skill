"""Direct Markdown/plain-text ingestion: no parsing needed, just normalize."""

from __future__ import annotations

from pathlib import Path

from mnemo.ingest import Chunk


def ingest_markdown(path: Path) -> list[Chunk]:
    """Read a Markdown/text file as a single Chunk, or none if it's blank."""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return [Chunk(text=text, source=path.name)]
