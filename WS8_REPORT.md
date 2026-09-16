# WS8 identity/revision remediation

## Addressed

- Added canonical source, segment, fact, and revision identity helpers.
- Persisted `CardID` and `RevisionHash` through Facts, generated cards, refined
  CSV rows, adapters, and Mnemo note types.
- Revision payloads include deck, content, metadata, and visible distractors.
- Canonical 64-character supplied hashes are recomputed at the adapter boundary
  when stale.
- Multiple cards emitted for one source unit receive distinct IDs.

## Verification

```text
unshare --user --map-root-user --net pytest -q -p no:cacheprovider \
  tests/test_identity.py tests/test_generate_flashcards.py tests/test_ai_authoring.py
75 passed
```

The full suite should be rerun by the orchestrator after integration.

## Residual risk

When a source unit emits multiple semantic variants without an explicit
per-variant intent, the suffix is occurrence-based (`variant-2`, etc.). This
avoids deriving persistent identity from editable wording, but reordering those
variants can move the suffix; a future authoring contract should provide an
explicit stable variant/recall intent.
