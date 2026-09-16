# WS9 — Anki compatibility

## Findings addressed

- Existing MONO models with an older, trailing-field schema now receive the
  missing fields through AnkiConnect `modelFieldAdd` before templates and CSS
  are updated.
- Existing models with reordered, extra, or otherwise incompatible fields are
  still rejected with a clear `AnkiConnectError`; no destructive migration is
  attempted.
- The refined CSV importer now uploads the bundled fonts referenced by
  `MONO_CSS`, while retaining collision detection for local media.

## Files changed

- `src/mnemo/anki/anki_connect.py`
- `src/mnemo/pipeline/import_refined_csv.py`
- `tests/test_anki_connect.py`
- `tests/test_import_refined_csv.py`

## Verification

```text
unshare --user --map-root-user --net pytest -q -p no:cacheprovider
349 passed
```

Focused AnkiConnect/refined-import tests also pass (`43 passed`). Tests use
mocked AnkiConnect responses and do not contact a live Anki instance.

## Residual risks

`modelFieldAdd` is intentionally limited to fields missing at the end of the
existing schema. A model with a custom field inserted in the middle must be
manually migrated or mapped explicitly. Live Anki behavior should still be
smoke-tested before broad use.

## Out of scope

Full model migration/renaming and automatic reconciliation of arbitrary
third-party note types remain out of scope.
