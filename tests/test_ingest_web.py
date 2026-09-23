"""Tests for web page ingestion (mnemo/ingest/web.py).

Network access is stubbed via monkeypatch on the trafilatura module functions
-- no live HTTP calls in tests.
"""

import pytest

from mnemo.ingest.web import WebIngestError, ingest_web


def test_ingest_web_returns_extracted_markdown(monkeypatch):
    import trafilatura

    monkeypatch.setattr(trafilatura, "fetch_url", lambda url: "<html>raw</html>")
    monkeypatch.setattr(
        trafilatura,
        "extract",
        lambda downloaded, output_format=None: "# Title\n\nSome article text.",
    )

    chunks = ingest_web("https://example.com/article")

    assert len(chunks) == 1
    assert chunks[0].text == "# Title\n\nSome article text."
    assert chunks[0].source == "https://example.com/article"


def test_ingest_web_raises_when_fetch_fails(monkeypatch):
    import trafilatura

    monkeypatch.setattr(trafilatura, "fetch_url", lambda url: None)

    with pytest.raises(WebIngestError, match="could not fetch"):
        ingest_web("https://example.com/missing")


def test_ingest_web_raises_when_no_content_extracted(monkeypatch):
    import trafilatura

    monkeypatch.setattr(trafilatura, "fetch_url", lambda url: "<html></html>")
    monkeypatch.setattr(trafilatura, "extract", lambda downloaded, output_format=None: None)

    with pytest.raises(WebIngestError, match="no extractable content"):
        ingest_web("https://example.com/blank")
