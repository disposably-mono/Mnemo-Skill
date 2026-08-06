# Task 4 Remediation Report

## Scope

Remediated the Task 4 package move regressions without altering flashcard
behavior. The direct script wrappers now locate the `src/` package layout,
bundled font resources work when imported from a zip distribution, and the
former `scripts.*` Anki module imports remain available as thin re-exports.

## RED Evidence

Command run before production changes:

```text
pytest tests/test_package_imports.py -q
```

Result: 7 existing tests passed and 9 new regression tests failed.

- `python -S scripts/import_cards.py --help`,
  `python -S scripts/export_note_types.py --help`, and
  `python -S scripts/import_refined_csv.py --help` each failed with
  `ModuleNotFoundError: No module named 'mnemo'`.
- The zip-resource regression produced paths that did not exist on disk.
- Imports for `scripts.adapter`, `scripts.anki_connect`,
  `scripts.genanki_export`, `scripts.media`, and `scripts.note_types` each
  failed with `ModuleNotFoundError`.

An additional root-cause check confirmed that merely exposing `src/` under
`python -S` next surfaced top-level `requests` and `genanki` imports. Those
imports were deferred to their live AnkiConnect and `.apkg` execution paths so
`--help` remains dependency-free; normal card import/export behavior remains
unchanged.

## Changes

- Updated `scripts/import_cards.py`, `scripts/export_note_types.py`, and
  `scripts/import_refined_csv.py` to add the repository `src/` directory for
  direct execution.
- Made `requests` and `genanki` imports lazy at the package operations that
  require them, allowing dependency-free help text under `python -S`.
- Updated `mnemo.anki.media.bundled_font_paths()` to materialize resources via
  `importlib.resources.as_file()`, copy them into a process-lifetime temporary
  directory with their CSS-required filenames, and retain that directory until
  process exit.
- Added compatibility-only `scripts/{adapter,anki_connect,genanki_export,
  media,note_types}.py` modules that re-export `mnemo.anki.*`; no business
  logic remains in the wrappers.
- Added subprocess regression coverage that does not rely on pytest's
  `pythonpath`, a zip-import resource test, and legacy import compatibility
  coverage in `tests/test_package_imports.py`.

## GREEN Evidence

Commands run after implementation:

```text
pytest tests/test_package_imports.py -q
```

Result: 16 passed.

```text
pytest tests/test_adapter.py tests/test_anki_connect.py tests/test_config.py tests/test_genanki_export.py tests/test_note_types.py tests/test_registry.py tests/test_import_cards.py tests/test_export_note_types.py tests/test_import_refined_csv.py tests/test_package_imports.py -q
```

Result: all selected tests passed (warnings only from third-party
`cached_property` deprecations).

```text
pytest --cov=mnemo --cov-report=term-missing --ignore=tests/test_generate_flashcards.py -q
```

Result: all collectable tests passed; total coverage was 81.04%.

```text
python -m compileall -q scripts src/mnemo
git diff --check
```

Result: both commands exited successfully.

## Files Changed

- `scripts/import_cards.py`
- `scripts/export_note_types.py`
- `scripts/import_refined_csv.py`
- `scripts/adapter.py`
- `scripts/anki_connect.py`
- `scripts/genanki_export.py`
- `scripts/media.py`
- `scripts/note_types.py`
- `src/mnemo/anki/anki_connect.py`
- `src/mnemo/anki/genanki_export.py`
- `src/mnemo/anki/media.py`
- `tests/test_package_imports.py`
- This report

## Commit

Commit: `fix: remediate anki package migration`.

## Concerns

The unfiltered command `pytest --cov=mnemo --cov-report=term-missing -q`
cannot collect `tests/test_generate_flashcards.py` because it imports the
unrelated missing legacy module `scripts.knowledge`. This remediation does not
own that later-wrapper issue and leaves it untouched. Excluding only that
uncollectable test file, the suite passes with 81.04% coverage.
