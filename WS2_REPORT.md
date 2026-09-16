# WS2 report — LLM pipeline

## Findings addressed

- T16: AI card drafts now require non-null, non-empty string fields, strict non-empty string tags, finite confidence in `0..1`, and optional fields cannot be null. A single surrounding JSON code fence is accepted; other malformed JSON remains rejected.
- T17: Answers must be supported by the selected verbatim evidence before card creation. AI supplied `source` and `topic` values are ignored in favor of source unit provenance. Prompts explicitly treat source units as untrusted data and prohibit provenance overrides.
- T18: Cornell candidate validation accepts legitimate short answers such as `ATP`, permits `follow_up_gaps: []`, rejects malformed gap/tag values, and supports an explicit `reviewed_paraphrase: true` policy marker for human-reviewed paraphrases. Unsupported answers still fail by default.

## Files changed

- `src/mnemo/pipeline/flashcards/authoring.py`
- `src/mnemo/pipeline/cornell.py`
- `tests/test_ai_authoring.py`
- `tests/test_cornell.py`

## Verification

- `pytest -q tests/test_ai_authoring.py tests/test_cornell.py` — 36 passed.
- `unshare --user --map-root-user --net pytest -q` — full suite passed.
- `git diff --check` — passed.

## Residual risks

The answer grounding check is deterministic substring matching. It blocks unrelated answers but cannot prove semantic entailment for paraphrases; those require the explicit review marker. JSON trailing-comma repair remains intentionally unsupported to avoid silently changing model output. The review marker is a contract field and should be set only by a trusted human review stage.

## Out-of-scope

Batching, caching, retries, model-side structured output, Anki import sequencing, and sidecar reconciliation remain assigned to other workstreams.
