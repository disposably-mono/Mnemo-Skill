"""Tests for PDF ingestion (mnemo/ingest/pdf.py).

Fixtures are built with real PyMuPDF documents rather than mocked, exercising
the actual parse paths (text, tables, math, images, scanned/vector pages).
"""

import shutil
from pathlib import Path

import pytest

from mnemo.ingest import ingest

_TESSERACT_AVAILABLE = shutil.which("tesseract") is not None


def test_pdf_yields_one_chunk_per_nonempty_page(tmp_path):
    import fitz

    pdf = tmp_path / "lecture.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Photosynthesis converts light.")
    doc.new_page()  # blank -> skipped
    doc.new_page().insert_text((72, 72), "ATP is energy currency.")
    doc.save(str(pdf))
    doc.close()

    chunks = ingest(pdf)

    assert len(chunks) == 2
    assert "Photosynthesis" in chunks[0].text
    assert chunks[0].source == "lecture.pdf p.1"
    assert "ATP" in chunks[1].text
    assert chunks[1].source == "lecture.pdf p.3"


def test_pdf_math_line_is_labeled(tmp_path):
    import fitz

    pdf = tmp_path / "physics.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "E = mc^2")
    doc.save(str(pdf))
    doc.close()

    chunks = ingest(pdf)

    assert any("[math:" in c.text for c in chunks)


def test_pdf_scanned_page_gets_visible_marker(tmp_path):
    import fitz

    pdf = tmp_path / "scan.pdf"
    doc = fitz.open()
    page = doc.new_page()
    # Insert a qualifying-size image with no text layer.
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100))
    pix.set_rect(pix.irect, (255, 0, 0))
    page.insert_image(fitz.Rect(0, 0, 100, 100), pixmap=pix)
    doc.save(str(pdf))
    doc.close()

    chunks = ingest(pdf)

    assert len(chunks) == 1
    assert "image-only page" in chunks[0].text
    assert "enable --ocr" in chunks[0].text


def test_pdf_extract_images_saves_qualifying_images(tmp_path):
    import fitz

    pdf = tmp_path / "figures.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "See the figure below.")
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 64, 64))
    pix.set_rect(pix.irect, (0, 255, 0))
    page.insert_image(fitz.Rect(200, 200, 264, 264), pixmap=pix)
    doc.save(str(pdf))
    doc.close()

    out_dir = tmp_path / "images"
    chunks = ingest(pdf, extract_images=out_dir)

    assert any("[figure:" in c.text for c in chunks)
    assert any(out_dir.iterdir())


def test_pdf_without_ocr_flag_leaves_scanned_page_unmarked_ocr(tmp_path):
    import fitz

    pdf = tmp_path / "scan2.pdf"
    doc = fitz.open()
    page = doc.new_page()
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 50, 50))
    pix.set_rect(pix.irect, (10, 10, 10))
    page.insert_image(fitz.Rect(0, 0, 50, 50), pixmap=pix)
    doc.save(str(pdf))
    doc.close()

    chunks = ingest(pdf, ocr=False)

    assert "(OCR)" not in chunks[0].source


def _scanned_page_pdf(tmp_path, text: str):
    """Build a PDF whose page has no text layer, only a rasterized image of
    the given text -- a real "scanned page" fixture for OCR tests."""
    import fitz

    render_doc = fitz.open()
    render_page = render_doc.new_page()
    render_page.insert_text((20, 40), text, fontsize=20)
    pix = render_page.get_pixmap(dpi=200)
    render_doc.close()

    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(page.rect, pixmap=pix)
    pdf = tmp_path / "scanned.pdf"
    doc.save(str(pdf))
    doc.close()
    return pdf


@pytest.mark.skipif(not _TESSERACT_AVAILABLE, reason="tesseract not installed")
def test_ocr_recovers_english_text_from_a_scanned_page(tmp_path):
    pdf = _scanned_page_pdf(tmp_path, "Photosynthesis converts light energy.")

    chunks = ingest(pdf, ocr=True)

    assert len(chunks) == 1
    assert "Photosynthesis" in chunks[0].text
    assert chunks[0].source.endswith("(OCR)")


@pytest.mark.skipif(not _TESSERACT_AVAILABLE, reason="tesseract not installed")
def test_ocr_with_filipino_language_pack_recovers_text(tmp_path):
    import fitz

    try:
        tessdata = fitz.get_tessdata()
    except RuntimeError:
        pytest.skip("tessdata directory not found")
    if not (Path(tessdata) / "fil.traineddata").exists():
        pytest.skip("tesseract-langpack-fil not installed")

    pdf = _scanned_page_pdf(tmp_path, "Ang mabilis na kayumangging soro.")

    chunks = ingest(pdf, ocr=True, language="fil")

    assert len(chunks) == 1
    assert chunks[0].text.strip()  # OCR produced some recognizable text
    assert chunks[0].source.endswith("(OCR)")
