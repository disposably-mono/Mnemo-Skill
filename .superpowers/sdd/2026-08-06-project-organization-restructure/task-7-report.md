# Task 7: Documentation Completion

## RED

Command:

```text
pytest tests/test_docs_consistency.py -q
```

Result: 1 failed. The new
`test_docs_reference_workspace_and_commands` reported that the documentation
set was missing `workspace/courses` and all five preferred `mnemo-*` commands.
The compatibility command `python scripts/ingest.py` was already present.

## GREEN

Command:

```text
pytest tests/test_docs_consistency.py -q
```

Result: 1 passed.

Command:

```text
rg -n "assets/fonts|python scripts/ingest.py|mnemo-ingest|workspace/courses" README.md SKILL.md docs
```

Result: the README, skill, and new reference docs contain the preferred command,
workspace, and compatibility references. The README font-license reference now
uses `src/mnemo/resources/fonts/LICENSE-*.txt`. Historical design and plan files
continue to mention the former `assets/fonts` path as migration context.

Additional verification: `git diff --check` passed before commit.

## Files Changed

- `README.md`: added concise workspace and preferred-command guidance, retained
  compatibility guidance, and corrected the bundled font license path.
- `SKILL.md`: documented preferred commands and compatibility wrappers, then
  updated workflow examples to use installed commands.
- `docs/architecture.md`: documented package namespaces, compatibility-wrapper
  boundaries, and the private course-first workspace.
- `docs/workflow.md`: documented the source-to-export workspace flow.
- `docs/naming-conventions.md`: documented course, module, source, note, card,
  JSONL, and Anki export naming examples.
- `tests/test_docs_consistency.py`: added a regression test for the required
  workspace and command references.

## Commit

- `5686668 docs: document package and workspace workflow`

## Concerns

- None.
