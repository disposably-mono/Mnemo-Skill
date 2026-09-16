# WS13 immutable knowledge planning

Added an immutable planning mode to `plan_knowledge()`:

- `mutate=False` clones every `SourceUnit` before enrichment.
- `return_units=True` returns the enriched clones alongside objectives and
  `KnowledgeUnit` records.
- Legacy callers retain the existing two-value, in-place behavior until they
  can migrate without breaking compatibility.

Regression coverage proves the original units remain unchanged and the
returned enriched units are distinct objects.

Verification:

```text
unshare --user --map-root-user --net pytest -q -p no:cacheprovider \
  tests/test_generate_flashcards.py
78 passed
```

Residual: production callers still use the compatibility mode; migrating them
to immutable mode is a follow-up API migration.
