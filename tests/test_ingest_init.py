"""Tests for the ingest dispatcher (mnemo/ingest/__init__.py).

ingest() dispatches by file extension to the right format-specific module and
returns normalized Chunk(text, source) records. Markdown/text is read
directly; other extensions delegate to their own ingest_<format> function.
"""

import pytest

from mnemo.ingest import Chunk, ingest


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        ingest("does-not-exist.md")


def test_unsupported_extension_raises(tmp_path):
    path = tmp_path / "notes.xyz"
    path.write_text("hello")
    with pytest.raises(ValueError, match="unsupported file type"):
        ingest(path)


def test_markdown_file_dispatches_to_text_ingest(tmp_path):
    path = tmp_path / "notes.md"
    path.write_text("# Biology\nQ: What is ATP?\nA: Adenosine triphosphate.\n")
    chunks = ingest(path)
    assert chunks == [
        Chunk(
            text="# Biology\nQ: What is ATP?\nA: Adenosine triphosphate.",
            source="notes.md",
        )
    ]


def test_txt_file_also_dispatches_to_text_ingest(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("plain text notes")
    chunks = ingest(path)
    assert chunks == [Chunk(text="plain text notes", source="notes.txt")]


def test_empty_text_file_yields_no_chunks(tmp_path):
    path = tmp_path / "empty.md"
    path.write_text("   \n\n")
    assert ingest(path) == []


def test_chunk_is_comparable_by_value():
    assert Chunk(text="a", source="b") == Chunk(text="a", source="b")


def test_docx_extension_dispatches_to_docx_ingest(tmp_path):
    import docx

    path = tmp_path / "notes.docx"
    document = docx.Document()
    document.add_paragraph("dispatched via extension")
    document.save(str(path))

    chunks = ingest(path)

    assert len(chunks) == 1
    assert chunks[0].source == "notes.docx"
