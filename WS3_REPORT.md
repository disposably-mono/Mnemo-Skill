# WS3 Anki remediation report

## Addressed findings

- T3: `AnkiNote` now retains the semantic Fact identity independently of editable fields; genanki uses it for stable GUIDs when a model has no CardID field.
- T5: refined CSV input is fully parsed and validated before note type, deck, preset, media, or note mutations; duplicate CardIDs in one input are rejected.
- T10: AnkiConnect can validate existing model fields before template/styling updates.
- T11: transport and invalid JSON failures now identify the AnkiConnect action.
- T12: NaN and infinity are rejected for image-occlusion coordinates.
- T2: cloze validation rejects zero/negative indices, empty bodies, unbalanced markers, and malformed residual cloze syntax.
- T22: refined passthrough rendering returns a new note rather than mutating the adapted note.

## Files changed

Production changes are in `adapter.py`, `anki_connect.py`, `genanki_export.py`, `card_schema.py`, and `import_refined_csv.py`. Focused regression tests were added to `test_card_schema.py` and `test_genanki_export.py`.

## Verification

```text
pytest -q tests/test_card_schema.py
32 passed

pytest -q tests/test_anki_connect.py tests/test_import_refined_csv.py tests/test_genanki_export.py tests/test_adapter.py
87 passed
```

## Residual risks / out of scope

- Live Anki update-in-place planning for models without a CardID field remains out of scope; AnkiConnect's default bundled models do not expose an identity field.
- Existing notes with incompatible refined models are detected before template updates, but additive schema migration is not implemented.
- Partial addNotes/deck-move reconciliation and font upload policy require broader importer changes and were not completed in this focused pass.
