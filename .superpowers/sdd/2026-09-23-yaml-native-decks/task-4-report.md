# Task 4 report — YAML-only public documentation

## Outcome

- Updated README, skill guidance, and the module template to use `.mnemo.yaml` manifests throughout.
- Documented required deck names and the `term-to-definition`, `definition-to-term`, and `both` draft directions, plus intentional lack of CSV input/export.
- Updated CLI draft help to describe its YAML output and changed the note renderer comment to refer to manifest fields.
- Added a CLI help contract test for `.mnemo.yaml`.

## Test evidence

- RED: `pytest tests/test_cli.py -k help -v` failed because `draft --help` did not mention `.mnemo.yaml`.
- GREEN: same command → 1 passed.
- Full suite: `pytest` → 266 passed, 20 dependency deprecation warnings.
- `git diff --check` passed.

## Self-review

- `rg` found no stale CSV workflow instructions in the public docs, template, or renderer comment. The remaining CSV mentions document unsupported input/export and test rejection behavior.
- No CRITICAL or HIGH findings identified in the scoped diff.
- Preexisting untracked `docs` and `uv.lock` were left untouched.
