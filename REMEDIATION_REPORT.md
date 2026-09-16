# Remediation report

## Integrated workstreams

Approved order was WS1 → WS2 → WS4 → WS5 → WS3. Each branch was isolated in
`.worktrees/`, rebased onto `main`, and retained for audit. The final merge
commits are `9ec75ac` (WS1), `7a74d13` (WS2), `2a8bb94` (WS4), `2f8485a`
(WS5), and `bce70e5` (WS3 integration). Detailed reports: [WS1](WS1_REPORT.md),
[WS2](WS2_REPORT.md), [WS3](WS3_REPORT.md), [WS4](WS4_REPORT.md), and
[WS5](WS5_REPORT.md).

Closed findings: T1, T2, T13, T14, T15, T16, T17, T18, T19, T20, T21, and the
completed portions of T3, T5, T10, T11, T12, and T22. The integrated cloze
validator retains both WS1 balanced/non-empty checks and WS3 residual-syntax
checks.

## Verification

Final isolated command:

```text
unshare --user --map-root-user --net pytest -q --cov=mnemo --cov-report=term -p no:cacheprovider
349 passed; 87.78% total coverage (80% threshold met)
```

`git diff --check` was clean. The existing test suite emits only dependency
deprecation warnings from `cached_property`.

## End-to-end sample

Using the real History 1 session (`workspace/courses/history-1/.../session.jsonl`),
24 validated Facts were loaded, adapted to MONO notes, and exported in a
no-network temporary `.apkg`: 24 notes, one deck (`Mnemo::History 1::Introduction to History`),
370,136 bytes, and a valid `collection.anki2`. The readiness gate on the real
CSV also passed all checks and import validation (24 notes, zero media).

The repository contains no raw LLM response artifact or configured API
credential, so the LLM call itself was not replayed; the deterministic
source/output stages were exercised with the preserved generated session.

## Deferred findings and residual risks

- T4/T6: live add/update planning and complete partial-failure reconciliation
  remain for a future Anki importer pass.
- T7/T8/T9/T10: full annotation preservation, additive model migration, and
  bundled-font upload policy are not complete in this pass.
- T14: borderless genuine PDF tables remain conservatively unstructured.
- T20: sidecars are aligned by unit IDs but are not yet fingerprinted.
- T22: immutable `plan_knowledge()` requires coordinated API changes.
- T23: media-root/remote-image policy still needs a dedicated security pass.

No branches or worktrees were deleted. The original untracked user artifacts
remain preserved in `stash@{0}` (`pre-remediation preserve untracked review artifacts`).
An earlier baseline test invocation contacted the configured Anki endpoint;
all post-remediation verification used network isolation and fake clients.

## Recommended next steps

Implement importer transaction/outcome reconciliation and CardID-based update
semantics first, then sidecar fingerprinting and security/media policy. Add a
recorded LLM response fixture to enable a truly reproducible full pipeline test.
