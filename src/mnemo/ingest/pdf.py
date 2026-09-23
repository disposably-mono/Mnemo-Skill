"""PDF ingestion via PyMuPDF: page text plus structured table/math/figure markers.

Ported from the pre-rewrite pipeline (proven, tested extraction logic) with
the KnowledgeUnit-era scope cut: this module only produces Chunks, it never
classifies content.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from mnemo.ingest import Chunk

_logger = logging.getLogger(__name__)

MIN_IMAGE_PX = 32
_GREEK = re.compile(r"[Ͱ-Ͽἀ-῿]")
_MATH_OPERATOR = re.compile(
    r"(?:[=+*^<>±×÷→↔∑∏√∝∞∫≈≠≤≥∂∇]|->|=>|<=|>=)"
)
_DISTINCTIVE_MATH = re.compile(
    r"[±×÷→↔∑∏√∝∞∫≈≠≤≥∂∇]"
)


def _scanned_page_marker(image_count: int, ocr_attempted: bool) -> str:
    """Visible placeholder for a page that carries images but no text layer."""
    plural = "image" if image_count == 1 else "images"
    remedy = (
        "OCR produced no text; transcribe manually"
        if ocr_attempted
        else "enable --ocr or transcribe manually"
    )
    return (
        f"[image-only page: no extractable text layer; {image_count} embedded "
        f"{plural}. Likely scanned or a figure. {remedy} before grounding cards "
        "here.]"
    )


def _vector_page_marker() -> str:
    """Visible placeholder for a page containing drawings but no text layer."""
    return (
        "[vector-only page: no extractable text layer; page contains vector "
        "drawings. Inspect or transcribe manually before grounding cards here.]"
    )


def _ocr_page_text(page, *, language: str = "eng") -> str:
    """Best-effort OCR of a single page; empty string when OCR is unavailable.

    ``language`` is a Tesseract language code (or "+"-joined codes, e.g.
    "eng+fil" for mixed English/Filipino text -- Tesseract's code for
    Filipino/Tagalog is "fil", not "tgl"). Requires the matching
    tesseract-langpack-<code> installed and findable via TESSDATA_PREFIX or
    the system tesseract install.
    """
    try:
        textpage = page.get_textpage_ocr(full=True, language=language)
        return page.get_text(textpage=textpage).strip()
    except Exception:
        _logger.debug("OCR failed for page; falling back to no OCR text", exc_info=True)
        return ""


def _format_pdf_table(rows: list[list[str | None]]) -> str:
    """Render extracted table rows as pipe-joined lines."""
    lines: list[str] = []
    for row in rows:
        line = " | ".join((cell or "").strip() for cell in row)
        if line.strip(" |"):
            lines.append(line)
    return "\n".join(lines)


def _has_table_grid(drawings: list[dict], bbox) -> bool:
    """Require drawing geometry around a candidate to avoid prose false tables."""
    try:
        import fitz

        table_rect = fitz.Rect(bbox)
    except Exception:
        return False
    for drawing in drawings:
        rect = drawing.get("rect")
        if rect is None or not table_rect.intersects(rect):
            continue
        if any(item and item[0] in {"l", "re"} for item in drawing.get("items", [])):
            return True
    return False


def _extract_pdf_tables(page) -> list[str]:
    """Structured pipe-row rendering of any tables PyMuPDF detects on a page."""
    try:
        finder = page.find_tables()
    except Exception:
        _logger.debug("PDF table detection failed for page", exc_info=True)
        return []
    blocks: list[str] = []
    try:
        drawings = page.get_drawings()
    except Exception:
        drawings = []
    for table in finder.tables:
        rows = table.extract()
        if len(rows) < 2 or max((len(row) for row in rows), default=0) < 2:
            continue
        bbox = getattr(table, "bbox", None)
        if bbox is None or not _has_table_grid(drawings, bbox):
            _logger.debug("retaining unstructured table candidate without a visible grid")
            blocks.append(
                "[table candidate: inferred columns without visible grid; "
                "human review required]"
            )
            continue
        rendered = _format_pdf_table(rows)
        if rendered:
            blocks.append(f"Table:\n{rendered}")
    return blocks


_URL_SCHEME = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://")


def _looks_like_pdf_math(text: str) -> bool:
    """Return true only for short text-layer lines with strong math signals."""
    value = " ".join(text.split())
    if not value or len(value) > 240:
        return False
    if _URL_SCHEME.search(value):
        return False
    operators = _MATH_OPERATOR.findall(value)
    if not operators:
        return False
    if _DISTINCTIVE_MATH.search(value):
        return True
    if _GREEK.search(value) and operators:
        return True
    if "=" in value and re.search(r"[A-Za-z0-9]", value):
        left, _, right = value.partition("=")
        return bool(left.strip() and right.strip())
    return len(operators) >= 2 and bool(re.search(r"[A-Za-z0-9]", value))


def _extract_pdf_math(page, source: str) -> list[str]:
    """Label likely equations while preserving text-layer span characters."""
    try:
        blocks = page.get_text("dict", sort=True).get("blocks", [])
    except Exception:
        _logger.debug("PDF math extraction failed for page %s", source, exc_info=True)
        return []
    markers: list[str] = []
    seen: set[str] = set()
    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            text = "".join(
                str(span.get("text", "")) for span in line.get("spans", [])
            ).strip()
            normalized = " ".join(text.split())
            if not _looks_like_pdf_math(normalized) or normalized in seen:
                continue
            seen.add(normalized)
            markers.append(f"[math: {normalized} | {source} text layer]")
    return markers


def _is_qualifying_image(info: dict) -> bool:
    """Heuristically reject tiny embedded assets that are usually decoration."""
    return info.get("width", 0) >= MIN_IMAGE_PX and info.get("height", 0) >= MIN_IMAGE_PX


def _extract_pdf_images(
    doc, page, path: Path, page_number: int, output: Path, source_identity: str
) -> list[str]:
    """Save qualifying page images and return auditable figure marker lines."""
    try:
        images = page.get_images(full=True)
    except Exception:
        _logger.debug(
            "listing embedded images failed for %s p.%s", path.name, page_number,
            exc_info=True,
        )
        return []
    markers: list[str] = []
    seen_xrefs: set[int] = set()
    for image in images:
        xref = image[0]
        if xref in seen_xrefs:
            continue
        seen_xrefs.add(xref)
        try:
            info = doc.extract_image(xref)
            if not _is_qualifying_image(info):
                continue
            image_number = len(markers) + 1
            filename = (
                f"{path.stem}-p{page_number}-img{image_number}-"
                f"{source_identity}.{info['ext']}"
            )
            saved = output / filename
            saved.write_bytes(info["image"])
        except Exception:
            _logger.debug(
                "extracting embedded image xref=%s failed for %s p.%s",
                xref, path.name, page_number, exc_info=True,
            )
            continue
        markers.append(f"[figure: {saved} | {path.name} p.{page_number}]")
    return markers


def ingest_pdf(
    path: Path,
    *,
    ocr: bool = False,
    extract_images: Path | None = None,
    language: str = "eng",
) -> list[Chunk]:
    """Ingest a PDF: one Chunk per non-blank page, with table/math/figure markers."""
    import fitz  # PyMuPDF

    chunks: list[Chunk] = []
    if extract_images is not None:
        extract_images.mkdir(parents=True, exist_ok=True)
    source_identity = hashlib.sha256(
        str(path.resolve()).encode("utf-8") + b"\0" + path.read_bytes()
    ).hexdigest()[:12]
    with fitz.open(str(path)) as doc:
        for index, page in enumerate(doc, start=1):
            source = f"{path.name} p.{index}"
            figures = (
                _extract_pdf_images(doc, page, path, index, extract_images, source_identity)
                if extract_images is not None
                else []
            )
            text = page.get_text().strip()
            if text:
                parts = [
                    text,
                    *_extract_pdf_tables(page),
                    *_extract_pdf_math(page, source),
                    *figures,
                ]
                chunks.append(Chunk(text="\n".join(parts), source=source))
                continue
            image_count = len(page.get_images(full=True))
            try:
                has_drawings = bool(page.get_drawings())
            except Exception:
                has_drawings = False
            if image_count == 0 and not has_drawings:
                continue
            if image_count == 0 and has_drawings:
                chunks.append(Chunk(text=_vector_page_marker(), source=source))
                continue
            ocr_text = _ocr_page_text(page, language=language) if ocr else ""
            if ocr_text:
                parts = [ocr_text, *figures]
                chunks.append(Chunk(text="\n".join(parts), source=f"{source} (OCR)"))
            else:
                marker = _scanned_page_marker(image_count, ocr_attempted=ocr)
                chunks.append(Chunk(text="\n".join([marker, *figures]), source=source))
    return chunks
