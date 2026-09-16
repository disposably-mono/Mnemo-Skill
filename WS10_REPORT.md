# WS10 — Transactional Anki import outcomes

## Findings addressed

- Sequential refined-CSV updates no longer abort at the first `updateNote`
  error. Successful updates are counted in `updated`; failures are retained
  in `failed_card_ids` and `failure_messages`.
- The refined importer CLI prints update failures and exits non-zero, while
  preserving the successful/failed split for callers that use the Python API.
- Existing notes with the same non-empty `CardID` are rejected before any
  import mutation. This avoids choosing an arbitrary note when a previous
  non-idempotent import created duplicates.

## Files changed

- `src/mnemo/pipeline/import_refined_csv.py`
- `tests/test_import_refined_csv.py`

## Verification

```text
unshare --user --map-root-user --net pytest -q \
  tests/test_import_refined_csv.py tests/test_anki_connect.py tests/test_import_cards.py
62 passed

unshare --user --map-root-user --net pytest -q -p no:cacheprovider
349 passed
```

## Residual risks / out of scope

- AnkiConnect's batch `addNotes` call is atomic only at the request/response
  boundary from the client's perspective. A transport failure after Anki has
  accepted some notes cannot be reconciled without querying Anki by stable
  `CardID`; this change leaves that existing error path explicit rather than
  guessing counts.
- A successful `updateNote` followed by a later process crash remains safe to
  retry because the next run resolves notes by `CardID` and updates them.
- Deck/preset/media setup still occurs before note writes, as required by the
  existing importer contract; making that whole sequence transactional is not
  supported by AnkiConnect.
