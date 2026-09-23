"""Web page ingestion via trafilatura: main-content extraction from a URL.

Not part of the extension-based ingest() dispatcher (there's no file path) --
called directly with a URL, e.g. from the CLI's ``mnemo ingest --url``.
"""

from __future__ import annotations

from mnemo.ingest import Chunk


class WebIngestError(RuntimeError):
    """Raised when a URL can't be fetched or has no extractable content."""


def ingest_web(url: str) -> list[Chunk]:
    """Fetch a URL and extract its main content as a single Chunk."""
    import trafilatura

    downloaded = trafilatura.fetch_url(url)
    if downloaded is None:
        raise WebIngestError(f"could not fetch {url}")
    text = trafilatura.extract(downloaded, output_format="markdown")
    if not text or not text.strip():
        raise WebIngestError(f"no extractable content at {url}")
    return [Chunk(text=text.strip(), source=url)]
