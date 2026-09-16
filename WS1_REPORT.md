# WS1 correctness remediation

## Findings addressed

- T1: import CLI tests now inject an unavailable fake AnkiConnect client, so
  the test suite does not contact live Anki or trigger sync.
- T2: cloze Facts require balanced markers with a positive index and a
  nonempty deletion body; malformed residual cloze prefixes are rejected.
- T19: list splitting now recognizes only top level commas/semicolons,
  preserves internal `and`/`or` alternatives, and ignores punctuation inside
  parentheses/brackets/braces.

## Files changed

- `src/mnemo/core/card_schema.py`
- `src/mnemo/pipeline/flashcards/text.py`
- `tests/test_card_schema.py`
- `tests/test_generate_flashcards.py`
- `tests/test_import_cards.py`

## Verification

```text
unshare --user --map-root-user --net pytest -q \
  tests/test_card_schema.py tests/test_generate_flashcards.py \
  tests/test_import_cards.py
........................................................................ [ 61%]
..............................................                           [100%]
```

All 118 scoped tests passed. The only output is an existing dependency
deprecation warning from `cached_property`.

## Residual risks

The list scanner treats unmatched grouping delimiters conservatively by
keeping separators inside the current depth; it does not reject malformed
source punctuation. Cloze nesting is intentionally unsupported because Anki
does not require nested deletions for these note types.

## Out of scope

Import preflight, note identity/update behavior, rendering/media handling,
coverage sidecars, and ingestion defects belong to the other workstreams.
