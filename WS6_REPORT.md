# WS6 importer remediation report

## Findings addressed

- T4: refined imports now resolve existing notes by stable `CardID` to their
  Anki note IDs and call `updateNote` instead of silently skipping changed
  cards. New cards continue through `addNotes` with duplicate protection.
- T6: `addNotes` results retain the CardIDs corresponding to `null` outcomes;
  the import report and CLI expose those IDs. Update failures include the
  affected CardID and note ID and abort rather than being swallowed.

## Files changed

- `src/mnemo/anki/anki_connect.py`
- `src/mnemo/pipeline/import_refined_csv.py`
- `tests/test_anki_connect.py`
- `tests/test_import_refined_csv.py`

## Verification

```text
PYTHONPATH=src pytest -q -p no:cacheprovider tests/test_anki_connect.py tests/test_import_refined_csv.py
40 passed

unshare --user --map-root-user --net pytest -q -p no:cacheprovider
349 passed
```

## Residual risks

- If an Anki collection contains duplicate notes with the same CardID, the
  current mapping uses the last response entry. A future migration should
  detect and report this ambiguity before updating.
- An update batch is intentionally sequential; if a later update fails, prior
  updates remain applied. The report identifies the failing CardID, but full
  transactional rollback is not available through AnkiConnect.
- The revision-hash and multi-card semantic identity findings reference an
  optional study-platform branch and files not present in this branch; they
  were not changed here.

## Out of scope

No Anki sync or live collection mutation was performed by the tests.
