# Remediation report

## Integrated workstreams

Approved order was WS1 → WS2 → WS4 → WS5 → WS3, followed by approved follow-up
workstreams WS6, WS7, WS8, WS9, and WS10. Each branch was isolated in
`.worktrees/`, rebased onto `main`, and retained for audit. The final merge
commits are `9ec75ac` (WS1), `7a74d13` (WS2), `2a8bb94` (WS4), `2f8485a`
(WS5), `bce70e5` (WS3 integration), `fea4ee3` (WS6), `93f40ea` (WS7),
`71b6385` (WS8), `1ecc5a7` (WS9), and `4d98891` (WS10).
Detailed reports: [WS1](WS1_REPORT.md),
[WS2](WS2_REPORT.md), [WS3](WS3_REPORT.md), [WS4](WS4_REPORT.md), and
[WS5](WS5_REPORT.md), [WS6](WS6_REPORT.md), [WS7](WS7_REPORT.md),
[WS8](WS8_REPORT.md), [WS9](WS9_REPORT.md), and [WS10](WS10_REPORT.md).

Closed findings: T1, T2, T3, T4, T5, T6, T10, T11, T12, T13, T14, T15, T16, T17,
T18, T19, T20, T21, and completed portions of T22. The integrated cloze
validator retains both WS1 balanced/non-empty checks and WS3 residual-syntax
checks.

## Verification

Final isolated command:

```text
unshare --user --map-root-user --net pytest -q --cov=mnemo --cov-report=term -p no:cacheprovider
349 passed; 87.72% total coverage (80% threshold met)
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

- T4/T6: CardID-based update and explicit partial-add outcomes are now handled;
  non-transactional sequential updates and transport-level batch ambiguity remain.
- T7/T8: full annotation preservation and multiline HTML policy remain limited
  for legacy note types. T9/T10 model migration and bundled-font upload are
  implemented for refined imports.
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
