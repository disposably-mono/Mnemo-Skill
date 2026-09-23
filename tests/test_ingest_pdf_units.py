"""Unit tests for mnemo/ingest/pdf.py private helpers, using lightweight fakes
for PyMuPDF objects where real table/OCR states are impractical to fabricate.
"""

from mnemo.ingest.pdf import (
    _extract_pdf_math,
    _extract_pdf_tables,
    _format_pdf_table,
    _has_table_grid,
    _looks_like_pdf_math,
    _ocr_page_text,
    _vector_page_marker,
    ingest_pdf,
)


def test_vector_page_marker_text():
    assert "vector-only page" in _vector_page_marker()


def test_format_pdf_table_drops_empty_rows():
    rendered = _format_pdf_table([["a", "b"], [None, None], ["c", "d"]])
    assert rendered == "a | b\nc | d"


class _FakePage:
    def get_textpage_ocr(self, full=True):
        raise RuntimeError("no tesseract")


def test_ocr_page_text_returns_empty_when_ocr_unavailable():
    assert _ocr_page_text(_FakePage()) == ""


class _FakeTable:
    def __init__(self, rows, bbox):
        self._rows = rows
        self.bbox = bbox

    def extract(self):
        return self._rows


class _FakeFinder:
    def __init__(self, tables):
        self.tables = tables


class _TablePage:
    def __init__(self, tables, drawings):
        self._tables = tables
        self._drawings = drawings

    def find_tables(self):
        return _FakeFinder(self._tables)

    def get_drawings(self):
        return self._drawings


def test_extract_pdf_tables_with_grid_renders_table(monkeypatch):
    import fitz

    bbox = fitz.Rect(0, 0, 100, 100)
    table = _FakeTable(rows=[["h1", "h2"], ["v1", "v2"]], bbox=bbox)
    drawing = {"rect": fitz.Rect(0, 0, 100, 100), "items": [("l", None)]}
    page = _TablePage(tables=[table], drawings=[drawing])

    blocks = _extract_pdf_tables(page)

    assert blocks == ["Table:\nh1 | h2\nv1 | v2"]


def test_extract_pdf_tables_without_grid_flags_candidate():
    import fitz

    bbox = fitz.Rect(0, 0, 100, 100)
    table = _FakeTable(rows=[["h1", "h2"], ["v1", "v2"]], bbox=bbox)
    page = _TablePage(tables=[table], drawings=[])

    blocks = _extract_pdf_tables(page)

    assert blocks == [
        "[table candidate: inferred columns without visible grid; human review required]"
    ]


def test_extract_pdf_tables_skips_single_row_or_column():
    page = _TablePage(tables=[_FakeTable(rows=[["only-row"]], bbox=None)], drawings=[])
    assert _extract_pdf_tables(page) == []


def test_has_table_grid_returns_false_on_bad_bbox():
    assert _has_table_grid([], bbox="not-a-rect") is False


def test_looks_like_pdf_math_rejects_empty_and_overlong():
    assert _looks_like_pdf_math("") is False
    assert _looks_like_pdf_math("x" * 300) is False


def test_looks_like_pdf_math_rejects_no_operators():
    assert _looks_like_pdf_math("just plain prose here") is False


def test_looks_like_pdf_math_accepts_greek_with_operator():
    assert _looks_like_pdf_math("α + β = γ") is True


def test_looks_like_pdf_math_accepts_equation_with_alnum_both_sides():
    assert _looks_like_pdf_math("F = ma") is True


def test_looks_like_pdf_math_rejects_equals_with_empty_side():
    assert _looks_like_pdf_math("= 5") is False


def test_looks_like_pdf_math_rejects_plain_url():
    assert _looks_like_pdf_math("http://example.com/module1/notes") is False


def test_looks_like_pdf_math_rejects_url_with_query_string():
    assert _looks_like_pdf_math("http://example.com?a=1&b=2") is False


def test_looks_like_pdf_math_rejects_file_path_with_slashes():
    assert _looks_like_pdf_math("notes/ch3/fig1") is False


class _MathPage:
    def get_text(self, mode, sort=True):
        return {
            "blocks": [
                {
                    "type": 0,
                    "lines": [
                        {"spans": [{"text": "E = mc^2"}]},
                        {"spans": [{"text": "E = mc^2"}]},  # duplicate -> deduped
                        {"spans": [{"text": "just prose"}]},
                    ],
                },
                {"type": 1, "lines": []},  # non-text block -> skipped
            ]
        }


def test_extract_pdf_math_dedupes_and_labels():
    markers = _extract_pdf_math(_MathPage(), source="doc.pdf p.1")
    assert markers == ["[math: E = mc^2 | doc.pdf p.1 text layer]"]


def test_ingest_pdf_vector_only_page_gets_marker(tmp_path, monkeypatch):
    import fitz

    pdf = tmp_path / "vector.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.draw_line(fitz.Point(0, 0), fitz.Point(50, 50))
    doc.save(str(pdf))
    doc.close()

    chunks = ingest_pdf(pdf)

    assert len(chunks) == 1
    assert "vector-only page" in chunks[0].text


def test_ingest_pdf_ocr_success_path_labels_source(tmp_path, monkeypatch):
    import fitz
    import mnemo.ingest.pdf as pdf_module

    pdf = tmp_path / "scan.pdf"
    doc = fitz.open()
    page = doc.new_page()
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 60, 60))
    pix.set_rect(pix.irect, (1, 2, 3))
    page.insert_image(fitz.Rect(0, 0, 60, 60), pixmap=pix)
    doc.save(str(pdf))
    doc.close()

    monkeypatch.setattr(pdf_module, "_ocr_page_text", lambda page: "recovered text")

    chunks = ingest_pdf(pdf, ocr=True)

    assert len(chunks) == 1
    assert chunks[0].text == "recovered text"
    assert chunks[0].source.endswith("(OCR)")


def test_ingest_pdf_fully_blank_page_yields_no_chunk(tmp_path):
    import fitz

    pdf = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf))
    doc.close()

    assert ingest_pdf(pdf) == []
