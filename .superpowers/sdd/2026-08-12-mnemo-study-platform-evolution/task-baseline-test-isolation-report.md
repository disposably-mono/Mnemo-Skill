# Baseline test isolation report

Date: 2026-08-12
Branch: `feat/study-platform-foundation`
Worktree: `/home/mono/Projects/Mnemo/.worktrees/study-platform-foundation`

## Scope

Targeted only the deterministic test/packaging assertions needed for the baseline failures:

- `tests/test_import_cards.py`
- `tests/test_package_imports.py`

No production files were changed.

## Root cause

1. `tests/test_import_cards.py::{test_cli_runs_as_documented_script,test_main_returns_zero_and_prints_fallback_summary}` assumed no local AnkiConnect server was running, so a live local Anki session flipped the path from `.apkg` fallback to successful live import.
2. `tests/test_package_imports.py::test_console_scripts_are_declared` inspected `importlib.metadata.entry_points()` from the active environment, which can drift from this checkout’s declared `pyproject.toml` metadata under editable installs or stale installs.

## RED evidence

Baseline reproduction before the test-only fix:

```text
$ pytest tests/test_import_cards.py -q
...F..........F

FAILED tests/test_import_cards.py::test_cli_runs_as_documented_script
FAILED tests/test_import_cards.py::test_main_returns_zero_and_prints_fallback_summary

Captured stdout:
Imported via AnkiConnect: 0 added, 2 skipped. AnkiWeb sync triggered.
```

Interpretation:

- The tests failed because the environment had a reachable local AnkiConnect server, so no `.apkg` file was produced.
- The packaging test was not failing in this environment, but it was still asserting the wrong contract (installed environment state instead of declared package metadata).

## Changes

### `tests/test_import_cards.py`

- Added `_UNREACHABLE_ANKI_URL = "http://127.0.0.1:1"`.
- Added `_write_unreachable_anki_config(...)` helper to force a local-but-unreachable AnkiConnect URL in CLI/main fallback tests.
- Updated:
  - `test_cli_runs_as_documented_script`
  - `test_main_returns_zero_and_prints_fallback_summary`
  - `test_main_reads_config_and_mappings_files`
- Tightened fallback assertions to check the reported `.apkg` path in stdout, not just process success.

### `tests/test_package_imports.py`

- Replaced `importlib.metadata.entry_points(group="console_scripts")` with a direct read of `[project.scripts]` from `pyproject.toml` via `tomllib`.
- Renamed the assertion to `test_console_scripts_are_declared_in_project_metadata`.
- Validated the full expected script mapping declared by this checkout.

## GREEN evidence

Focused verification:

```text
$ pytest tests/test_import_cards.py -q
...............                                                          [100%]

$ pytest tests/test_package_imports.py -q
.................................                                        [100%]
```

Full verification:

```text
$ pytest -q
..................................                                       [100%]
```

Notes:

- Full suite passed.
- Existing warnings remain from `cached_property` under Python 3.14; this task did not modify them.

## Self-review

- The Anki fallback tests now control their own connectivity assumption instead of depending on ambient machine state.
- The packaging test now verifies the package declaration this repository owns, which matches the test’s intent better than checking whichever distribution happens to be installed.
- Kept the change minimal and test-only.

## Concerns

- `http://127.0.0.1:1` is a deliberately unreachable local endpoint in practice and fixed the nondeterminism here; if an unusual environment actively serves HTTP on port 1, these tests would need a different reserved local endpoint strategy.
