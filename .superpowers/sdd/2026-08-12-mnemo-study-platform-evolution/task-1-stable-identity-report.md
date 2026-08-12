# Track 1 Stable Identity Report

Date: 2026-08-12
Branch: `feat/study-platform-foundation`
Worktree: `/home/mono/Projects/Mnemo/.worktrees/study-platform-foundation`

## Scope completed

Implemented Release 1 / Track 1 foundations for:

- pure, immutable identity helpers in `src/mnemo/core/identity.py`
- `Fact` support for persisted `revision_hash`
- Mnemo-owned note-type persistence of `CardID` and `RevisionHash`
- adapter placeholder support for `{revision_hash}`
- refined CSV propagation of `RevisionHash`
- flashcard CSV/export propagation of stable semantic `CardID` plus `RevisionHash`

Kept Track 1 scoped to content-addressed identities only. I did not add any
logical-source resolution or catalog-backed source identity creation; that
remains Track 2 work.

## RED evidence

New test-first file added:

- `tests/test_identity.py`

Initial RED command:

```bash
pytest tests/test_identity.py -q
```

Observed failure:

```text
E   ModuleNotFoundError: No module named 'mnemo.core.identity'
```

This confirmed the new Track 1 surface did not exist yet.

## GREEN evidence

After implementing the minimal production slice:

```bash
pytest tests/test_identity.py -q
```

Result:

```text
7 passed
```

Focused compatibility verification:

```bash
pytest tests/test_identity.py tests/test_card_schema.py tests/test_adapter.py tests/test_note_types.py tests/test_registry.py tests/test_import_refined_csv.py tests/test_genanki_export.py tests/test_generate_flashcards.py -q
```

Result:

```text
182 passed
```

Broader required verification with coverage:

```bash
pytest --cov
```

Result:

```text
352 passed
TOTAL ... 88%
Required test coverage of 80.0% reached.
```

## Files added

- `src/mnemo/core/identity.py`
- `tests/test_identity.py`

## Files changed

- `src/mnemo/core/card_schema.py`
- `src/mnemo/anki/note_types.py`
- `src/mnemo/anki/adapter.py`
- `src/mnemo/pipeline/import_refined_csv.py`
- `src/mnemo/pipeline/flashcards/models.py`
- `src/mnemo/pipeline/flashcards/render.py`
- `src/mnemo/pipeline/flashcards/authoring.py`
- `tests/test_genanki_export.py`

## Design decisions

1. `Fact.id` remains the persisted FactID surface for compatibility.
   - Existing import/export flows already understand `id`/`CardID`.
   - Track 1 adds `revision_hash` rather than renaming the existing identity field.

2. `revision_hash` is stored as explicit Fact metadata.
   - It round-trips through JSONL/Fact serialization.
   - Adapter placeholders can use persisted hashes directly.

3. Semantic FactID and editorial revision are separated.
   - Fact IDs for generated flashcards now prefer `fact_id(unit_id, recall_intent, fact_type)`.
   - Legacy front/back/source hashing remains as a fallback when no semantic unit id exists.

4. Mnemo-owned note types store identities silently.
   - `CardID` and `RevisionHash` were added as fields to MONO and refined note types.
   - Templates were not changed to display revision hashes.

5. External mappings were kept backward compatible.
   - Existing mappings that only reference `Front`/`Back` still work unchanged.
   - New `{revision_hash}` placeholder is available when needed.

6. Refined CSV revisions are derived from rendered row content when absent.
   - This keeps legacy refined CSV imports compatible.
   - Image passthrough fields remain part of revision detection there.

## Requirement mapping

- `source_version_id(logical_source_id, normalized_bytes)`:
  implemented in `src/mnemo/core/identity.py`
- `segment_id(source_version_id, location, text)`:
  implemented in `src/mnemo/core/identity.py`
- `fact_id(unit_id, recall_intent, fact_type)`:
  implemented in `src/mnemo/core/identity.py` and used by flashcard generation
- `revision_hash(rendered_fact)`:
  implemented in `src/mnemo/core/identity.py` and propagated through Facts,
  note types, adapter placeholders, refined CSV, and generated card exports

## Self-review

- Track 2 boundary respected: yes
- Pure/immutable helper implementation: yes
- Existing external mappings/defaults unexpectedly changed: no
- Mnemo-owned note types persist `CardID`: yes
- Mnemo-owned note types persist `RevisionHash`: yes
- Fact serialization compatibility preserved: yes
- Full suite + coverage re-run after changes: yes

## Notes / concerns

- `ruff` was not available in this environment (`command not found`), so lint
  verification was limited to test/coverage and manual diff review.
- The fallback adapter revision payload for generic Fact imports excludes deck
  identity intentionally; refined CSV and generated-card flows compute and carry
  explicit revision hashes so visible card changes still propagate correctly.

## Review follow-up fixes

Follow-up date: 2026-08-12

Addressed two HIGH consistency findings without expanding beyond Track 1.

### Finding 1: refined CSV fallback used a non-canonical revision payload

Problem:

- refined CSV fallback used a local `_revision_payload()`
- it hashed `type` instead of `card_type`
- it omitted `learning_purpose`
- it hashed `Confidence` as a CSV string instead of the normalized numeric value

Fix:

- added shared helper module `src/mnemo/pipeline/flashcards/revisions.py`
- moved canonical rendered-card payload construction there
- added `rendered_card_revision_hash_from_row()` so `row_to_fact()` rebuilds the
  same normalized payload from generated CSV rows
- row reconstruction now unescapes text fields and normalizes confidence to a
  float where possible

RED:

```bash
pytest tests/test_import_refined_csv.py::test_row_to_fact_preserves_generated_revision_hash_when_csv_field_is_blank -q
```

Observed:

```text
AssertionError: fact.revision_hash != card.revision_hash
```

GREEN:

```bash
pytest tests/test_import_refined_csv.py::test_row_to_fact_preserves_generated_revision_hash_when_csv_field_is_blank -q
```

Result:

```text
1 passed
```

### Finding 2: AI authoring hashed escaped metadata while deterministic cards did not

Problem:

- AI authoring hashed escaped topic/source metadata
- deterministic revision hashing used raw topic/source metadata
- logically equivalent cards could therefore produce different revision hashes

Fix:

- AI authoring now builds revision hashes from the same shared raw canonical
  rendered-card payload before HTML escaping
- deterministic generation now also computes revision hashes from raw logical
  fields before escaping, using the same helper
- shared raw extra/context derivation now comes from render logic so both paths
  agree on fallback context text

RED:

```bash
pytest tests/test_ai_authoring.py::test_json_ai_author_matches_deterministic_revision_hash_for_logically_equivalent_card -q
```

Observed:

```text
AssertionError: authored.revision_hash != deterministic.revision_hash
```

GREEN:

```bash
pytest tests/test_ai_authoring.py::test_json_ai_author_matches_deterministic_revision_hash_for_logically_equivalent_card -q
```

Result:

```text
1 passed
```

### Covering verification after fixes

Focused impacted suites:

```bash
pytest tests/test_import_refined_csv.py tests/test_ai_authoring.py tests/test_generate_flashcards.py tests/test_identity.py -q
```

Result:

```text
103 passed
```

Final full-suite verification:

```bash
pytest --cov
```

Result:

```text
354 passed
TOTAL ... 88.12%
Required test coverage of 80.0% reached.
```

### Review follow-up 2: image-supported generated rows still mismatched on blank RevisionHash

Follow-up date: 2026-08-12

Problem:

- generated image-supported cards still hashed the `Back` field including the
  rendered `<img>` presentation markup
- row reconstruction unescaped `Back`, so URL/alt values containing `&`, `<`,
  or similar characters changed the reconstructed payload
- this left a remaining mismatch when importing a generated row with blank
  `RevisionHash`

Fix:

- kept image fields as first-class logical inputs in the canonical payload
- normalized canonical `back` for image-supported cards by stripping the
  rendered image suffix in either escaped generated form or unescaped row form
- this makes revision hashing depend on the text answer plus `image_url` /
  `image_alt`, not duplicated presentation markup

RED:

```bash
pytest tests/test_import_refined_csv.py::test_row_to_fact_preserves_generated_revision_hash_for_image_supported_cards -q
```

Observed:

```text
AssertionError: fact.revision_hash != card.revision_hash
```

GREEN:

```bash
pytest tests/test_import_refined_csv.py::test_row_to_fact_preserves_generated_revision_hash_for_image_supported_cards -q
```

Result:

```text
1 passed
```

Covering verification after this fix:

```bash
pytest tests/test_import_refined_csv.py tests/test_generate_flashcards.py tests/test_identity.py tests/test_ai_authoring.py -q
```

Result:

```text
104 passed
```

Fresh full-suite verification:

```bash
pytest --cov
```

Result:

```text
355 passed
TOTAL ... 88.21%
Required test coverage of 80.0% reached.
```
