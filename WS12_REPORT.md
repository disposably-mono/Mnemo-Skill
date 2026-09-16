# WS12 explicit card variants

Added an optional `SourceUnit.variant_id` and corresponding AI prompt/response
field. When provided, it becomes part of the stable semantic CardID, avoiding
occurrence-based identity for intentionally distinct variants. Existing inputs
remain compatible; occurrence fallback is retained for legacy units.

`plan_knowledge()` was reviewed but not made immutable: existing callers rely
on its in-place enrichment of `SourceUnit` objects, so changing that contract
requires coordinated API changes.

Verification:

```text
unshare --user --map-root-user --net pytest -q -p no:cacheprovider \
  tests/test_generate_flashcards.py tests/test_ai_authoring.py
94 passed
```
