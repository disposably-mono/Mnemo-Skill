"""Tests for page-range restriction and Filipino/English filtering on PDF
ingestion (mnemo/ingest/pdf.py's `pages` and `prose_language` params)."""

from mnemo.ingest import ingest


def _make_pdf(tmp_path, page_texts):
    import fitz

    pdf = tmp_path / "doc.pdf"
    doc = fitz.open()
    for text in page_texts:
        doc.new_page().insert_text((72, 72), text)
    doc.save(str(pdf))
    doc.close()
    return pdf


def test_pages_restricts_to_the_given_inclusive_range(tmp_path):
    pdf = _make_pdf(tmp_path, ["Page one text.", "Page two text.", "Page three text."])

    chunks = ingest(pdf, pages=(1, 2))

    assert [c.source for c in chunks] == ["doc.pdf p.1", "doc.pdf p.2"]


def test_pages_range_beyond_document_length_is_clamped(tmp_path):
    pdf = _make_pdf(tmp_path, ["Only page."])

    chunks = ingest(pdf, pages=(1, 100))

    assert len(chunks) == 1


def test_pages_none_ingests_every_page(tmp_path):
    pdf = _make_pdf(tmp_path, ["Page one.", "Page two."])

    chunks = ingest(pdf)

    assert len(chunks) == 2


def test_prose_language_keeps_only_matching_pages(tmp_path):
    fil_text = "Ang wikang panturo ay ginagamit sa mga eskuwelahan at sa pagtuturo."
    eng_text = "The medium of instruction is used in schools and for teaching."
    pdf = _make_pdf(tmp_path, [fil_text, eng_text, fil_text])

    chunks = ingest(pdf, prose_language="fil")

    assert [c.source for c in chunks] == ["doc.pdf p.1", "doc.pdf p.3"]


def test_prose_language_keeps_unknown_pages_rather_than_dropping_them(tmp_path):
    # A page with no language signal (e.g. a table of figures) must not be
    # silently discarded just because it can't be classified confidently.
    pdf = _make_pdf(tmp_path, ["42 100 7 2024"])

    chunks = ingest(pdf, prose_language="fil")

    assert len(chunks) == 1


def test_pages_and_prose_language_combine(tmp_path):
    fil_text = "Ang wikang panturo ay ginagamit sa mga eskuwelahan at sa pagtuturo."
    eng_text = "The medium of instruction is used in schools and for teaching."
    pdf = _make_pdf(tmp_path, [fil_text, eng_text, fil_text, eng_text, fil_text])

    chunks = ingest(pdf, pages=(1, 3), prose_language="fil")

    assert [c.source for c in chunks] == ["doc.pdf p.1", "doc.pdf p.3"]
