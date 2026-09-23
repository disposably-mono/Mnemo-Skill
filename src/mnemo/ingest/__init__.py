"""Source ingestion: study material -> normalized text chunks with provenance.

Turns a file into uniform Chunks (text + a human-readable source label) that
the agent reads to author cards. Dispatch is by file extension; each format
gets its own module (markdown.py, pdf.py, pptx.py, docx.py). Web pages are
ingested by URL via ingest.web.ingest_web(), not through this dispatcher.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_TEXT_EXTS = {".md", ".markdown", ".txt", ".text"}


@dataclass
class Chunk:
    """A normalized unit of source text with its provenance."""

    text: str
    source: str


def ingest(
    path: str | Path,
    *,
    ocr: bool = False,
    extract_images: Path | None = None,
) -> list[Chunk]:
    """Parse a source file into normalized text chunks. Dispatch by extension.

    ``ocr`` and ``extract_images`` only affect PDFs.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    ext = path.suffix.lower()
    if ext in _TEXT_EXTS:
        from mnemo.ingest.markdown import ingest_markdown

        return ingest_markdown(path)
    if ext == ".pdf":
        from mnemo.ingest.pdf import ingest_pdf

        return ingest_pdf(path, ocr=ocr, extract_images=extract_images)
    if ext == ".pptx":
        from mnemo.ingest.pptx import ingest_pptx

        return ingest_pptx(path)
    if ext == ".docx":
        from mnemo.ingest.docx import ingest_docx

        return ingest_docx(path)
    raise ValueError(f"unsupported file type: {path.suffix!r} ({path.name})")
