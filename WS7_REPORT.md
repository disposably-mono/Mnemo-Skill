# WS7 Sidecar Integrity Report

## Findings addressed

- T20 residual: generated manifest and objective-coverage sidecars now carry a
  SHA-256 fingerprint of the exact CSV they describe.
- The readiness gate rejects missing/stale fingerprints and rejects manifest /
  coverage sidecars with different objective ID sets.

## Files changed

- `src/mnemo/pipeline/flashcards/io.py`: streaming SHA-256 helper.
- `src/mnemo/pipeline/flashcards/cli.py`: emit CSV fingerprints in manifest and
  coverage sidecars.
- `src/mnemo/pipeline/ready.py`: validate freshness and objective alignment.
- `tests/test_ready_gate.py`: regression tests for stale CSV and coverage data.

## Verification

```text
unshare --user --map-root-user --net pytest -q -p no:cacheprovider
349 passed
```

Focused readiness and generation tests also passed.

## Residual risks

Older generated sidecars without `fingerprints.csv_sha256` are intentionally
rejected by `mnemo-ready`; regenerate those decks. Fingerprints cover the CSV
and semantic sidecars, but do not yet fingerprint the source material or
settings/violations sidecars.
