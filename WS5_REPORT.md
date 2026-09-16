# WS5 validation report

## Findings addressed

- T20: readiness now requires a manifest and verifies every CSV `KnowledgeUnitID` is present in that manifest. Missing source fields are preserved as missing so the audit emits `MISSING_SOURCE` instead of inventing a CSV row location.
- T21: FSRS learning steps are normalized to minutes, so `1440m`, `24h`, and `1d` are all rejected as day length or longer.
- T22: deferred. `plan_knowledge()` currently annotates mutable `SourceUnit` instances and downstream renderers rely on those annotations. Making the function immutable requires a coordinated API change outside this validation workstream.
- T6: no production Anki changes were made because partial import accounting is owned by the Anki importer workstream; this is an explicit scope boundary.

## Files changed

- `src/mnemo/pipeline/audit_cards.py`
- `src/mnemo/pipeline/ready.py`
- `src/mnemo/pipeline/flashcards/validate.py`
- Focused regression tests in `tests/test_card_quality.py`, `tests/test_ready_gate.py`, and `tests/test_generate_flashcards.py`.

## Verification

```text
unshare --user --map-root-user --net pytest -q tests/test_ready_gate.py tests/test_card_quality.py tests/test_generate_flashcards.py
121 passed

unshare --user --map-root-user --net pytest -q -p no:cacheprovider
349 passed
```

## Residual risks

Coverage sidecars are still not fingerprinted; readiness currently binds the manifest to the CSV by unit IDs. A future coordinated change should add source/card fingerprints to all generated sidecars and validate objective IDs against the current cards.
