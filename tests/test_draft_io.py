"""Tests for writing deferred units to a plain deferred.md (mnemo/draft.py)."""

from mnemo.draft import DeferredUnit, write_deferred


def test_write_deferred_creates_readable_markdown(tmp_path):
    path = tmp_path / "deferred.md"
    units = [
        DeferredUnit(text="Mitochondria have a complex structure.", source="notes.md",
                     reason="no confident grounding pattern matched"),
        DeferredUnit(text="Some other prose.", source="lecture.pdf p.2",
                     reason="no confident grounding pattern matched"),
    ]

    write_deferred(path, units)
    content = path.read_text()

    assert "notes.md" in content
    assert "Mitochondria have a complex structure." in content
    assert "lecture.pdf p.2" in content
    assert "no confident grounding pattern matched" in content


def test_write_deferred_with_no_units_writes_empty_notice(tmp_path):
    path = tmp_path / "deferred.md"
    write_deferred(path, [])
    assert "no deferred" in path.read_text().lower()


def test_write_deferred_fences_text_containing_heading_syntax(tmp_path):
    path = tmp_path / "deferred.md"
    units = [
        DeferredUnit(
            text="## Injected Heading\nsome slide title text",
            source="slide.pptx",
            reason="no confident grounding pattern matched",
        )
    ]
    write_deferred(path, units)
    content = path.read_text()

    # The injected "## " line must sit inside a code fence, so a Markdown
    # renderer treats it as inert text rather than a real document heading.
    lines = content.splitlines()
    injected_index = lines.index("## Injected Heading")
    assert lines[injected_index - 1].startswith("```")
    assert lines[injected_index + 2].startswith("```")


def test_write_deferred_escapes_heading_syntax_in_source(tmp_path):
    path = tmp_path / "deferred.md"
    units = [DeferredUnit(text="body", source="## weird source", reason="r")]

    write_deferred(path, units)
    content = path.read_text()

    heading_lines = [line for line in content.splitlines() if line.startswith("## ")]
    assert heading_lines == ["## weird source"]
