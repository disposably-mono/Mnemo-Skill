"""Unit tests for mnemo/ingest/pptx.py private helpers, covering group shapes
and chart rendering that are awkward to fabricate through a saved .pptx file.
"""

from mnemo.ingest.pptx import _extract_pptx_chart, _format_chart_value, _shape_parts


def test_format_chart_value_integers_and_floats_and_none():
    assert _format_chart_value(None) == ""
    assert _format_chart_value(5.0) == "5"
    assert _format_chart_value(3.14159) == "3.14159"
    assert _format_chart_value("raw") == "raw"


class _Category:
    def __init__(self, label):
        self.label = label


class _Series:
    def __init__(self, name, values):
        self.name = name
        self.values = values


class _Plot:
    def __init__(self, categories):
        self.categories = categories


class _TitleFrame:
    def __init__(self, text):
        self.text_frame = self

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        self._text = value


class _Chart:
    def __init__(self, title, series, categories):
        self.has_title = bool(title)
        if title:
            frame = _TitleFrame(title)
            frame.text = title
            self.chart_title = frame
        self.series = series
        self.plots = [_Plot(categories)]


def test_extract_pptx_chart_renders_title_categories_and_series():
    chart = _Chart(
        title="Population",
        series=[_Series("2020", [10, 20]), _Series("2021", [15, 25])],
        categories=[_Category("Town A"), _Category("Town B")],
    )

    rendered = _extract_pptx_chart(chart)

    assert "Chart:" in rendered
    assert "Title: Population" in rendered
    assert "Category | 2020 | 2021" in rendered
    assert "Town A | 10 | 15" in rendered


def test_extract_pptx_chart_without_categories_lists_series_only():
    chart = _Chart(title="", series=[_Series("A", [1])], categories=[])
    rendered = _extract_pptx_chart(chart)
    assert rendered == "Chart:\nSeries: A"


class _FakeShape:
    def __init__(
        self,
        shape_type="OTHER",
        text=None,
        table_rows=None,
        chart=None,
        subshapes=None,
    ):
        self.shape_type = shape_type
        self._text = text
        self.has_text_frame = text is not None
        self.has_table = table_rows is not None
        self.has_chart = chart is not None
        self.chart = chart
        self.shapes = subshapes or []
        if text is not None:
            self.text_frame = _TitleFrame(text)
            self.text_frame.text = text
        if table_rows is not None:
            self.table = _FakeTable(table_rows)


class _FakeCell:
    def __init__(self, text):
        self.text = text


class _FakeRow:
    def __init__(self, cells):
        self.cells = [_FakeCell(cell) for cell in cells]


class _FakeTable:
    def __init__(self, rows):
        self.rows = [_FakeRow(row) for row in rows]


def test_shape_parts_recurses_into_group_shapes(monkeypatch):
    class _FakeMSO:
        GROUP = "GROUP"

    monkeypatch.setattr("pptx.enum.shapes.MSO_SHAPE_TYPE", _FakeMSO, raising=False)

    inner = _FakeShape(shape_type="GROUP", subshapes=[_FakeShape(text="nested text")])
    parts = _shape_parts([inner])

    assert parts == ["nested text"]


def test_shape_parts_extracts_table_text():
    shape = _FakeShape(table_rows=[["A", "B"], ["1", "2"]])
    parts = _shape_parts([shape])

    assert parts == ["A | B\n1 | 2"]
