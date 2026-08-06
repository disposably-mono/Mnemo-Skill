# Task 6: Compatibility Wrappers Completion

## RED

Command:

```text
pytest tests/test_package_imports.py tests/test_export_note_types.py tests/test_import_refined_csv.py -q
```

Result: 35 passed, 1 failed. The new
`test_export_note_types_wrapper_reexports_package_api` failed because
`scripts.export_note_types` did not expose `export_note_types`.

## GREEN

Command:

```text
pytest tests/test_package_imports.py tests/test_export_note_types.py tests/test_import_refined_csv.py -q
```

Result: 36 passed. Pytest emitted 24 existing `DeprecationWarning`s from the
installed `cached_property` dependency.

Command:

```text
wc -l scripts/*.py
```

Result: compatibility wrappers are 12 lines each, except
`scripts/export_note_types.py` at 14 lines. All wrappers are under 20 lines.

Additional verification: `git diff --check` passed, and no
`scripts.adapter` references remain in
`src/mnemo/pipeline/import_refined_csv.py`.

## Files Changed

- `scripts/export_note_types.py`: re-exports `export_note_types` and `main`
  and defines `__all__ = ["export_note_types", "main"]`.
- `src/mnemo/pipeline/import_refined_csv.py`: corrected two stale documentation
  references to `mnemo.anki.adapter`.
- `tests/test_package_imports.py`: added the wrapper API identity and `__all__`
  regression test.

## Commit

- `4a522b1 fix: complete compatibility wrappers`

## Concerns

- The focused tests pass with 24 existing dependency deprecation warnings from
  `cached_property`; this task did not modify that dependency or warning source.
