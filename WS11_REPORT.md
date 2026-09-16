# WS11 output and media hardening

## Addressed

- The default QA adapter now preserves optional `Extra`, `Context`, and
  `Mnemonic` annotations in a safely escaped answer-side block when targeting
  the stock MONO Basic model.
- Image-occlusion media paths explicitly reject remote URL schemes and remain
  constrained to the configured local media root.

## Verification

```text
unshare --user --map-root-user --net pytest -q -p no:cacheprovider \
  tests/test_adapter.py tests/test_identity.py
48 passed
```

## Residual risk

Remote `ImageURL` values in refined CSV remain an explicit supported feature;
they are HTML-escaped and are not fetched by Mnemo. A future deployment may
want an opt-in allowlist or local-download policy.
