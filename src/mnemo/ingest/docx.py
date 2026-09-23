"""DOCX ingestion via mammoth: whole-document raw text, one Chunk per file."""

from __future__ import annotations

from pathlib import Path

from mnemo.ingest import Chunk


def ingest_docx(path: Path) -> list[Chunk]:
    """Read a Word document as a single Chunk, or none if it's blank."""
    import mammoth

    with path.open("rb") as fh:
        result = mammoth.extract_raw_text(fh)
    text = result.value.strip()
    if not text:
        return []
    return [Chunk(text=text, source=path.name)]
