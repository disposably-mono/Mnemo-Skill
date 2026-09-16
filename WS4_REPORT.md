# WS4 Ingestion Report

## Findings addressed

- T13: PDF pages containing only vector drawings now produce an auditable
  `vector-only page` marker. PPTX extraction recursively traverses nested
  group shapes, preserving text inside grouped content.
- T14: PDF table candidates are emitted only when PyMuPDF reports visible line
  or rectangle geometry intersecting the candidate bounds. Prose-only false
  table detections are therefore suppressed while bordered tables remain
  structured.
- T15: Extracted PDF image filenames include a short identity derived from the
  resolved source path and source bytes, preventing same-basename collisions
  in a shared output directory.

## Files changed

- `src/mnemo/pipeline/ingest.py`
- `tests/test_ingest.py`

## Verification

- `pytest -q tests/test_ingest.py` — 29 passed.
- `unshare --user --map-root-user --net pytest -q -p no:cacheprovider` — full
  suite passed (349 tests).
- `git diff --check` — passed.

## Residual risks

- Borderless genuine PDF tables without detectable drawing geometry are
  conservatively omitted from structured re-emission. A future extractor can
  add a confidence path based on cell coordinates.
- Existing consumers that hard-code extracted image filenames must use the
  figure markers or glob the identity suffix.

## Out of scope

- AI prompting, Anki adapters/import behavior, and sidecar validation were
  left to their assigned workstreams.
