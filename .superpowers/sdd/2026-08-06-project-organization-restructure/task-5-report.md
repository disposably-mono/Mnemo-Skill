# Task 5 Report: Move Pipeline Modules And CLI

## Status

DONE

## RED Verification

Command:

```bash
pytest tests/test_ingest.py tests/test_generate_flashcards.py tests/test_card_quality.py tests/test_calibrate.py tests/test_import_cards.py tests/test_import_refined_csv.py tests/test_export_note_types.py -q
```

Result: failed during collection with seven expected `ModuleNotFoundError`
errors. The missing modules were `mnemo.pipeline.ingest`,
`mnemo.pipeline.generate_flashcards`, `mnemo.pipeline.audit_cards`,
`mnemo.pipeline.calibrate`, `mnemo.pipeline.import_cards`,
`mnemo.pipeline.import_refined_csv`, and
`mnemo.pipeline.export_note_types`.

## Implementation

- Moved the seven workflow modules into `src/mnemo/pipeline/`.
- Updated intra-pipeline imports to package imports and retained core and Anki
  package imports.
- Wired every requested `mnemo.cli` module directly to its package `main`.
- Replaced the original workflow scripts with thin direct-command compatibility
  wrappers that bootstrap `src`, import package `main`, and execute it only
  when run as a script.
- Updated pipeline-related tests to import package modules. Package import
  tests now assert that CLI entrypoints re-export their matching pipeline main,
  and verify direct `--help` support for all seven compatibility scripts.
- Preserved the Task 4 Anki shims and their regression coverage unchanged.

## GREEN Verification

Commands and results:

```bash
pytest tests/test_ingest.py tests/test_generate_flashcards.py tests/test_card_quality.py tests/test_calibrate.py tests/test_import_cards.py tests/test_import_refined_csv.py tests/test_export_note_types.py -q
```

Passed: 120 tests. The run emitted 44 third-party `cached_property`
deprecation warnings.

```bash
pytest tests/test_package_imports.py -q
```

Passed: 20 tests, including direct script execution under `python -S`.

```bash
python -m pip install -e .
mnemo-ingest --help
mnemo-generate --help
mnemo-audit --help
mnemo-import --help
mnemo-export-note-types --help
```

Passed: editable installation succeeded and every console command printed its
real CLI usage and exited zero.

```bash
pytest --cov=mnemo --cov-report=term-missing
```

Passed: 254 tests passed; total coverage was 87.19%, exceeding the 80%
requirement. The run emitted 56 third-party `cached_property` deprecation
warnings.

```bash
python -m compileall -q src/mnemo scripts
git diff --check
git diff --cached --check
```

Passed without syntax or whitespace errors.

## Files Changed

- `src/mnemo/pipeline/{ingest,generate_flashcards,audit_cards,calibrate,import_cards,import_refined_csv,export_note_types}.py`
- `scripts/{ingest,generate_flashcards,audit_cards,calibrate,import_cards,import_refined_csv,export_note_types}.py`
- `src/mnemo/cli/{ingest,generate,audit,import_cards,export_note_types}.py`
- `tests/test_ingest.py`
- `tests/test_generate_flashcards.py`
- `tests/test_card_quality.py`
- `tests/test_calibrate.py`
- `tests/test_import_cards.py`
- `tests/test_import_refined_csv.py`
- `tests/test_export_note_types.py`
- `tests/test_genanki_export.py`
- `tests/test_package_imports.py`

## Commits

- `536c250 refactor: move pipeline modules into package`

## Concerns

None. The only observed warnings are third-party `cached_property`
deprecations under Python 3.14; they predate this task and do not affect test
results.
