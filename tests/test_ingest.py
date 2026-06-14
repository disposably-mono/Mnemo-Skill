"""Tests for source ingestion (scripts/ingest.py).

Fixtures are built programmatically with the real libraries (PyMuPDF for PDF,
python-pptx for slides) rather than mocked, so these exercise the actual parse
paths. Markdown/text is read directly.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.ingest import Chunk, ingest

_REPO_ROOT = Path(__file__).resolve().parent.parent


def test_markdown_is_read_as_a_single_chunk(tmp_path):
    md = tmp_path / "notes.md"
    md.write_text("# Title\n\nThe mitochondria is the powerhouse of the cell.\n")

    chunks = ingest(md)

    assert len(chunks) == 1
    assert isinstance(chunks[0], Chunk)
    assert "powerhouse" in chunks[0].text
    assert chunks[0].source == "notes.md"


def test_plain_text_is_supported(tmp_path):
    txt = tmp_path / "scratch.txt"
    txt.write_text("just some pasted notes")
    chunks = ingest(txt)
    assert chunks[0].text == "just some pasted notes"
    assert chunks[0].source == "scratch.txt"


def test_pdf_yields_one_chunk_per_nonempty_page(tmp_path):
    import fitz  # PyMuPDF

    pdf = tmp_path / "lecture.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Photosynthesis converts light.")
    doc.new_page()  # intentionally blank -> should be skipped
    doc.new_page().insert_text((72, 72), "ATP is energy currency.")
    doc.save(str(pdf))
    doc.close()

    chunks = ingest(pdf)

    assert len(chunks) == 2  # blank page dropped
    assert "Photosynthesis" in chunks[0].text
    assert chunks[0].source == "lecture.pdf p.1"
    assert "ATP" in chunks[1].text
    assert chunks[1].source == "lecture.pdf p.3"  # provenance keeps real page no.


def test_pptx_yields_one_chunk_per_slide_with_all_shape_text(tmp_path):
    from pptx import Presentation
    from pptx.util import Inches

    pptx = tmp_path / "deck.pptx"
    prs = Presentation()
    blank = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1))
    box.text_frame.text = "Newton's first law: inertia."
    prs.save(str(pptx))

    chunks = ingest(pptx)

    assert len(chunks) == 1
    assert "inertia" in chunks[0].text
    assert chunks[0].source == "deck.pptx slide 1"


def test_pptx_includes_tables_and_existing_speaker_notes(tmp_path):
    from pptx import Presentation
    from pptx.util import Inches

    pptx = tmp_path / "structured.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    table = slide.shapes.add_table(2, 2, Inches(1), Inches(1), Inches(5), Inches(2)).table
    table.cell(0, 0).text = "Metric"
    table.cell(0, 1).text = "Meaning"
    table.cell(1, 0).text = "ROI"
    table.cell(1, 1).text = "Return on investment"
    slide.notes_slide.notes_text_frame.text = "Explain why cost belongs in the denominator."
    prs.save(str(pptx))

    chunks = ingest(pptx)

    assert "Metric | Meaning" in chunks[0].text
    assert "ROI | Return on investment" in chunks[0].text
    assert "Speaker notes:" in chunks[0].text
    assert "cost belongs in the denominator" in chunks[0].text


def test_unknown_extension_raises(tmp_path):
    weird = tmp_path / "image.png"
    weird.write_bytes(b"\x89PNG")
    with pytest.raises(ValueError, match="unsupported"):
        ingest(weird)


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        ingest(tmp_path / "nope.md")


def test_cli_prints_provenance_and_text(tmp_path):
    md = tmp_path / "notes.md"
    md.write_text("Krebs cycle happens in the mitochondria.")

    proc = subprocess.run(
        [sys.executable, "scripts/ingest.py", str(md)],
        cwd=_REPO_ROOT, capture_output=True, text=True,
    )

    assert proc.returncode == 0, proc.stderr
    assert "notes.md" in proc.stdout
    assert "Krebs cycle" in proc.stdout
