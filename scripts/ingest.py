"""Source ingestion: study material -> normalized text chunks with provenance.

This is the Anki-agnostic front of the pipeline. It turns a file into uniform
``Chunk``s (``text`` + a human-readable ``source`` like ``lecture.pdf p.4``) that
Claude then reads to author Facts. Markdown/plain text is read directly; PDFs go
through PyMuPDF (one chunk per page); slide decks through python-pptx (one chunk
per slide). SKILL.md step 2 runs:

    python scripts/ingest.py <file>
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):  # allow `python scripts/ingest.py <file>`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_TEXT_EXTS = {".md", ".markdown", ".txt", ".text"}


@dataclass
class Chunk:
    """A normalized unit of source text with its provenance."""

    text: str
    source: str


def ingest(path: str | Path) -> list[Chunk]:
    """Parse a source file into normalized text chunks. Dispatch by extension."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    ext = path.suffix.lower()
    if ext in _TEXT_EXTS:
        return _ingest_text(path)
    if ext == ".pdf":
        return _ingest_pdf(path)
    if ext == ".pptx":
        return _ingest_pptx(path)
    raise ValueError(f"unsupported file type: {path.suffix!r} ({path.name})")


def _ingest_text(path: Path) -> list[Chunk]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return [Chunk(text=text, source=path.name)]


def _ingest_pdf(path: Path) -> list[Chunk]:
    import fitz  # PyMuPDF

    chunks: list[Chunk] = []
    with fitz.open(str(path)) as doc:
        for index, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            if text:  # skip blank pages
                chunks.append(Chunk(text=text, source=f"{path.name} p.{index}"))
    return chunks


def _ingest_pptx(path: Path) -> list[Chunk]:
    from pptx import Presentation

    chunks: list[Chunk] = []
    prs = Presentation(str(path))
    for index, slide in enumerate(prs.slides, start=1):
        parts: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text.strip():
                parts.append(shape.text_frame.text)
            elif shape.has_table:
                rows = [
                    " | ".join(cell.text.strip() for cell in row.cells)
                    for row in shape.table.rows
                ]
                table = "\n".join(row for row in rows if row.strip(" |"))
                if table:
                    parts.append(table)
            elif shape.has_chart:
                chart = shape.chart
                chart_parts: list[str] = []
                if chart.has_title and chart.chart_title.text_frame.text.strip():
                    chart_parts.append(chart.chart_title.text_frame.text.strip())
                chart_parts.extend(
                    str(series.name).strip()
                    for series in chart.series
                    if str(series.name).strip()
                )
                if chart_parts:
                    parts.append("Chart: " + " | ".join(chart_parts))
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                parts.append(f"Speaker notes:\n{notes}")
        text = "\n".join(parts).strip()
        if text:  # skip empty slides
            chunks.append(Chunk(text=text, source=f"{path.name} slide {index}"))
    return chunks


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Normalize study material into text chunks with provenance."
    )
    parser.add_argument("file", help="Path to a .pdf, .pptx, .md, or .txt source.")
    args = parser.parse_args(argv)

    for chunk in ingest(args.file):
        print(f"--- {chunk.source} ---")
        print(chunk.text)
        print()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
