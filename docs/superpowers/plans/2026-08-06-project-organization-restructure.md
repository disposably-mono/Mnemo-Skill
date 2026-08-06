# Project Organization Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure Mnemo into a maintainable `src/mnemo/` package with a course-first private workspace, tracked templates, stable naming rules, compatibility script wrappers, and updated docs/tests.

**Architecture:** Separate package code from study workspace data. Move implementation modules into `mnemo.core`, `mnemo.anki`, and `mnemo.pipeline`; keep `scripts/*.py` as thin compatibility wrappers; add `workspace/` templates with ignore rules that keep real course materials private.

**Tech Stack:** Python 3.11+, pytest, pytest-cov, setuptools `src` layout, pyproject console scripts, importlib.resources, Markdown docs, YAML templates.

## Global Constraints

- Real course materials, Cornell notes, card drafts, and exports are gitignored.
- Workspace templates, metadata, README files, and `.gitkeep` placeholders are tracked.
- Existing `python scripts/*.py` commands remain supported.
- Preferred console scripts are `mnemo-ingest`, `mnemo-generate`, `mnemo-audit`, `mnemo-import`, and `mnemo-export-note-types`.
- Business logic lives under `src/mnemo/`, not in wrapper scripts.
- Use `importlib.resources` for package-owned fonts.
- Existing flashcard behavior must not change.
- Coverage remains at or above 80%.

### Task 1: Workspace Scaffold

**Files:**
- Modify: `.gitignore`
- Create: `workspace/README.md`
- Create: `workspace/courses/_template/README.md`
- Create: `workspace/courses/_template/course.yaml`
- Create: `workspace/courses/_template/00-module-template/README.md`
- Create: `workspace/courses/_template/00-module-template/module.yaml`
- Create: `workspace/courses/_template/00-module-template/source-materials/.gitkeep`
- Create: `workspace/courses/_template/00-module-template/cornell-notes/cornell-note.template.md`
- Create: `workspace/courses/_template/00-module-template/cards/.gitkeep`
- Create: `workspace/courses/_template/00-module-template/exports/.gitkeep`
- Test: `tests/test_workspace_structure.py`

**Interfaces:**
- Produces tracked templates and ignore rules for private course data.

- [ ] **Step 1: Write failing tests**

Create `tests/test_workspace_structure.py` with three tests:

- `test_workspace_template_files_exist`: assert every file listed above exists.
- `test_workspace_private_outputs_are_ignored`: run `git check-ignore` for sample files in `source-materials/`, `cornell-notes/`, `cards/`, and `exports/`, then assert all are ignored.
- `test_workspace_templates_are_not_ignored`: run `git check-ignore` for the tracked README, YAML, template Markdown, and `.gitkeep` files, then assert stdout is empty.

- [ ] **Step 2: Verify red**

Run: `pytest tests/test_workspace_structure.py -q`

Expected: FAIL because the workspace and ignore rules do not exist.

- [ ] **Step 3: Add ignore rules**

Append to `.gitignore`:

```gitignore
# Mnemo workspace private study files
workspace/courses/**/source-materials/*
workspace/courses/**/cornell-notes/*
workspace/courses/**/cards/*
workspace/courses/**/exports/*

# Keep workspace scaffolding and templates tracked
!workspace/
!workspace/README.md
!workspace/courses/
!workspace/courses/_template/
!workspace/courses/**/README.md
!workspace/courses/**/*.yaml
!workspace/courses/**/*.template.md
!workspace/courses/**/.gitkeep
```

- [ ] **Step 4: Add templates**

Create `workspace/README.md` with this content: explain that templates and
metadata are tracked, real study files are ignored, and users should copy
`courses/_template` per course and `00-module-template` per module.

Create `workspace/courses/_template/course.yaml`:

```yaml
courseSlug: course-slug
courseTitle: Course Title
term: 2026-term
defaultDeck: Mnemo::Course Title
tags:
  - course-tag
```

Create `workspace/courses/_template/00-module-template/module.yaml`:

```yaml
moduleSlug: 00-module-template
moduleTitle: Module Title
courseSlug: course-slug
sourceStatus: pending
noteStatus: pending
cardStatus: pending
tags:
  - module-tag
```

Create `workspace/courses/_template/00-module-template/cornell-notes/cornell-note.template.md`:

```markdown
---
courseSlug: course-slug
moduleSlug: 00-module-template
noteDate: 2026-08-06
sourceFiles: []
tags:
  - module-tag
---

# Module Title Cornell Notes

## Source References

- `source-materials/example.pdf`

## Cues

| Cue | Notes |
| --- | --- |
| What is the central question for this module? | Replace this with grounded notes from the source. |

## Notes

Write concise source-grounded notes here.

## Summary

Summarize the module in five sentences or fewer.

## Follow-Up Gaps

- List unclear or unsupported points that need another source.

## Candidate Cards

- Front: Replace with one atomic recall prompt.
  Back: Replace with one independently gradable answer.
  Extra: Explanation: Replace with why the answer is true.
```

Create short README files for `courses/_template/` and `00-module-template/`
describing copy/rename usage. Create `.gitkeep` files in `source-materials/`,
`cards/`, and `exports/`.

- [ ] **Step 5: Verify green and commit**

Run:

```bash
pytest tests/test_workspace_structure.py -q
git add .gitignore workspace tests/test_workspace_structure.py
git commit -m "feat: add course workspace scaffold"
```

### Task 2: Package Scaffold

**Files:**
- Modify: `pyproject.toml`
- Create: `src/mnemo/**/__init__.py`
- Create: `src/mnemo/cli/{ingest,generate,audit,import_cards,export_note_types}.py`
- Test: `tests/test_package_imports.py`

**Interfaces:**
- Produces importable `mnemo` package and declared console scripts.

- [ ] **Step 1: Write failing tests**

Create `tests/test_package_imports.py`:

```python
import importlib.metadata

import mnemo


def test_package_exposes_version():
    assert mnemo.__version__ == "0.0.1"


def test_console_scripts_are_declared():
    scripts = {
        entry_point.name
        for entry_point in importlib.metadata.entry_points(group="console_scripts")
    }
    assert "mnemo-ingest" in scripts
    assert "mnemo-generate" in scripts
    assert "mnemo-audit" in scripts
    assert "mnemo-import" in scripts
    assert "mnemo-export-note-types" in scripts
```

- [ ] **Step 2: Verify red**

Run: `pytest tests/test_package_imports.py -q`

Expected: FAIL because `mnemo` is not importable.

- [ ] **Step 3: Add package and pyproject config**

Create `src/mnemo/__init__.py`:

```python
"""Mnemo source-grounded study tooling."""

__version__ = "0.0.1"
```

Create namespace `__init__.py` files in `core`, `anki`, `pipeline`, `cli`, and `resources` with a one-line docstring.

Add to `pyproject.toml` while preserving existing metadata:

```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project.scripts]
mnemo-ingest = "mnemo.cli.ingest:main"
mnemo-generate = "mnemo.cli.generate:main"
mnemo-audit = "mnemo.cli.audit:main"
mnemo-import = "mnemo.cli.import_cards:main"
mnemo-export-note-types = "mnemo.cli.export_note_types:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
"mnemo.resources.fonts" = ["*.txt", "*.ttf"]
```

Change pytest and coverage config to:

```toml
[tool.pytest.ini_options]
pythonpath = ["src", "."]
testpaths = ["tests"]
addopts = "-q"

[tool.coverage.run]
source = ["src/mnemo"]
branch = true
```

- [ ] **Step 4: Add temporary CLI stubs**

Each `src/mnemo/cli/*.py` should expose a `main` that raises a clear temporary error:

```python
"""Temporary CLI entrypoint."""


def main(argv: list[str] | None = None) -> int:
    raise SystemExit("Mnemo CLI entrypoint is not wired yet")
```

- [ ] **Step 5: Verify green and commit**

Run:

```bash
python -m pip install -e .
pytest tests/test_package_imports.py -q
git add pyproject.toml src tests/test_package_imports.py
git commit -m "chore: add mnemo package scaffold"
```

### Task 3: Move Core Modules

**Files:**
- Move: `scripts/{card_schema,knowledge,verbatim,config}.py`
- Modify: `tests/test_card_schema.py`, `tests/test_config.py`, `tests/test_knowledge.py`, `tests/test_registry.py`

**Interfaces:**
- Produces `mnemo.core.card_schema`, `mnemo.core.knowledge`, `mnemo.core.verbatim`, and `mnemo.core.config`.

- [ ] **Step 1: Update tests to fail on package imports**

Replace test imports:

```text
scripts.card_schema -> mnemo.core.card_schema
scripts.knowledge -> mnemo.core.knowledge
scripts.config -> mnemo.core.config
```

Update `tests/test_registry.py` to import:

```python
from mnemo.anki import adapter
from mnemo.core import config
from mnemo.core.card_schema import FACT_TYPES, Fact
```

Run: `pytest tests/test_card_schema.py tests/test_knowledge.py -q`

Expected: FAIL because core modules have not moved.

- [ ] **Step 2: Move files and update imports**

Run:

```bash
git mv scripts/card_schema.py src/mnemo/core/card_schema.py
git mv scripts/knowledge.py src/mnemo/core/knowledge.py
git mv scripts/verbatim.py src/mnemo/core/verbatim.py
git mv scripts/config.py src/mnemo/core/config.py
```

Replace imports:

```text
scripts.knowledge -> mnemo.core.knowledge
scripts.verbatim -> mnemo.core.verbatim
scripts.adapter -> mnemo.anki.adapter
```

- [ ] **Step 3: Verify and commit**

Run:

```bash
pytest tests/test_card_schema.py tests/test_knowledge.py -q
git add src/mnemo/core tests/test_card_schema.py tests/test_config.py tests/test_knowledge.py tests/test_registry.py
git add -u scripts
git commit -m "refactor: move core modules into package"
```

---

### Task 4: Move Anki Modules And Fonts

**Files:**
- Move: `scripts/{adapter,anki_connect,genanki_export,media,note_types}.py`
- Move: `assets/fonts/*`
- Modify: Anki-related tests

**Interfaces:**
- Produces `mnemo.anki.*` modules and packaged font resources.

- [ ] **Step 1: Update tests to fail on package imports**

Replace test imports:

```text
scripts.adapter -> mnemo.anki.adapter
scripts.anki_connect -> mnemo.anki.anki_connect
scripts.genanki_export -> mnemo.anki.genanki_export
scripts.media -> mnemo.anki.media
scripts.note_types -> mnemo.anki.note_types
scripts.card_schema -> mnemo.core.card_schema
```

Run:

```bash
pytest tests/test_adapter.py tests/test_anki_connect.py tests/test_config.py tests/test_genanki_export.py tests/test_note_types.py -q
```

Expected: FAIL because Anki modules have not moved.

- [ ] **Step 2: Move files**

Run:

```bash
git mv scripts/adapter.py src/mnemo/anki/adapter.py
git mv scripts/anki_connect.py src/mnemo/anki/anki_connect.py
git mv scripts/genanki_export.py src/mnemo/anki/genanki_export.py
git mv scripts/media.py src/mnemo/anki/media.py
git mv scripts/note_types.py src/mnemo/anki/note_types.py
mkdir -p src/mnemo/resources/fonts
git mv assets/fonts/* src/mnemo/resources/fonts/
```

- [ ] **Step 3: Update imports and resources**

Replace module imports:

```text
scripts.adapter -> mnemo.anki.adapter
scripts.anki_connect -> mnemo.anki.anki_connect
scripts.card_schema -> mnemo.core.card_schema
scripts.genanki_export -> mnemo.anki.genanki_export
scripts.media -> mnemo.anki.media
scripts.note_types -> mnemo.anki.note_types
```

In `src/mnemo/anki/media.py`, make `bundled_font_paths()` read package resources:

```python
from importlib import resources
from pathlib import Path


def bundled_font_paths() -> list[Path]:
    font_root = resources.files("mnemo.resources.fonts")
    return sorted(
        Path(str(path))
        for path in font_root.iterdir()
        if path.name.endswith(".ttf")
    )
```

- [ ] **Step 4: Verify and commit**

Run:

```bash
pytest tests/test_adapter.py tests/test_anki_connect.py tests/test_config.py tests/test_genanki_export.py tests/test_note_types.py tests/test_registry.py -q
git add src/mnemo/anki src/mnemo/resources tests pyproject.toml
git add -u scripts assets
git commit -m "refactor: move anki modules into package"
```

---

### Task 5: Move Pipeline Modules And CLI

**Files:**
- Move: `scripts/{ingest,generate_flashcards,audit_cards,import_cards,import_refined_csv,calibrate,export_note_types}.py`
- Modify: `src/mnemo/cli/*.py`
- Modify: pipeline-related tests

**Interfaces:**
- Produces `mnemo.pipeline.*` modules and working `mnemo-*` console commands.

- [ ] **Step 1: Update tests to fail on package imports**

Replace test imports:

```text
scripts.audit_cards -> mnemo.pipeline.audit_cards
scripts.calibrate -> mnemo.pipeline.calibrate
scripts.generate_flashcards -> mnemo.pipeline.generate_flashcards
scripts.import_cards -> mnemo.pipeline.import_cards
scripts.import_refined_csv -> mnemo.pipeline.import_refined_csv
scripts.ingest -> mnemo.pipeline.ingest
scripts.export_note_types -> mnemo.pipeline.export_note_types
```

Run:

```bash
pytest tests/test_ingest.py tests/test_generate_flashcards.py tests/test_card_quality.py tests/test_calibrate.py tests/test_import_cards.py tests/test_import_refined_csv.py tests/test_export_note_types.py -q
```

Expected: FAIL because pipeline modules have not moved.

- [ ] **Step 2: Move files and update imports**

Run:

```bash
git mv scripts/ingest.py src/mnemo/pipeline/ingest.py
git mv scripts/generate_flashcards.py src/mnemo/pipeline/generate_flashcards.py
git mv scripts/audit_cards.py src/mnemo/pipeline/audit_cards.py
git mv scripts/import_cards.py src/mnemo/pipeline/import_cards.py
git mv scripts/import_refined_csv.py src/mnemo/pipeline/import_refined_csv.py
git mv scripts/calibrate.py src/mnemo/pipeline/calibrate.py
git mv scripts/export_note_types.py src/mnemo/pipeline/export_note_types.py
```

Replace imports:

```text
scripts.adapter -> mnemo.anki.adapter
scripts.anki_connect -> mnemo.anki.anki_connect
scripts.audit_cards -> mnemo.pipeline.audit_cards
scripts.calibrate -> mnemo.pipeline.calibrate
scripts.card_schema -> mnemo.core.card_schema
scripts.config -> mnemo.core.config
scripts.generate_flashcards -> mnemo.pipeline.generate_flashcards
scripts.genanki_export -> mnemo.anki.genanki_export
scripts.import_refined_csv -> mnemo.pipeline.import_refined_csv
scripts.knowledge -> mnemo.core.knowledge
scripts.media -> mnemo.anki.media
scripts.note_types -> mnemo.anki.note_types
scripts.verbatim -> mnemo.core.verbatim
```

- [ ] **Step 3: Wire CLI modules**

Use this pattern:

```python
"""Command-line entrypoint for source ingestion."""

from mnemo.pipeline.ingest import main

__all__ = ["main"]
```

Map CLI files:

```text
src/mnemo/cli/ingest.py -> mnemo.pipeline.ingest:main
src/mnemo/cli/generate.py -> mnemo.pipeline.generate_flashcards:main
src/mnemo/cli/audit.py -> mnemo.pipeline.audit_cards:main
src/mnemo/cli/import_cards.py -> mnemo.pipeline.import_cards:main
src/mnemo/cli/export_note_types.py -> mnemo.pipeline.export_note_types:export_note_types, main
```

- [ ] **Step 4: Verify and commit**

Run:

```bash
pytest tests/test_ingest.py tests/test_generate_flashcards.py tests/test_card_quality.py tests/test_calibrate.py tests/test_import_cards.py tests/test_import_refined_csv.py tests/test_export_note_types.py -q
python -m pip install -e .
mnemo-ingest --help
mnemo-generate --help
mnemo-audit --help
mnemo-import --help
mnemo-export-note-types --help
git add src/mnemo/pipeline src/mnemo/cli tests pyproject.toml
git add -u scripts
git commit -m "refactor: move pipeline modules into package"
```

---

### Task 6: Compatibility Wrappers

**Files:**
- Recreate: `scripts/*.py`
- Modify: direct invocation tests

**Interfaces:**
- Produces script commands that delegate to package modules.

- [ ] **Step 1: Add failing wrapper tests**

Add to `tests/test_package_imports.py`:

```python
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_compatibility_scripts_print_help():
    scripts = [
        "scripts/generate_flashcards.py",
        "scripts/audit_cards.py",
        "scripts/import_cards.py",
        "scripts/export_note_types.py",
    ]
    for script in scripts:
        result = subprocess.run(
            [sys.executable, script, "--help"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()
```

Run: `pytest tests/test_package_imports.py tests/test_ingest.py tests/test_import_cards.py -q`

Expected: FAIL until wrappers exist.

- [ ] **Step 2: Create wrappers**

Use this pattern for each wrapper:

```python
"""Compatibility wrapper for `python scripts/ingest.py`."""

from mnemo.pipeline.ingest import main


if __name__ == "__main__":
    raise SystemExit(main())
```

Wrapper mappings:

```text
scripts/ingest.py -> mnemo.pipeline.ingest:main
scripts/generate_flashcards.py -> mnemo.pipeline.generate_flashcards:main
scripts/audit_cards.py -> mnemo.pipeline.audit_cards:main
scripts/import_cards.py -> mnemo.pipeline.import_cards:main
scripts/import_refined_csv.py -> mnemo.pipeline.import_refined_csv:main
scripts/calibrate.py -> mnemo.pipeline.calibrate:main
scripts/export_note_types.py -> mnemo.pipeline.export_note_types:main
```

For `scripts/export_note_types.py`, also expose:

```python
from mnemo.pipeline.export_note_types import export_note_types, main

__all__ = ["export_note_types", "main"]
```

- [ ] **Step 3: Verify wrappers and commit**

Run:

```bash
pytest tests/test_package_imports.py tests/test_ingest.py tests/test_import_cards.py -q
wc -l scripts/*.py
git add scripts tests
git commit -m "refactor: keep compatibility script wrappers"
```

Expected: wrapper tests pass and every wrapper is under 20 lines.

---

### Task 7: Documentation

**Files:**
- Create: `docs/architecture.md`
- Create: `docs/workflow.md`
- Create: `docs/naming-conventions.md`
- Modify: `README.md`
- Modify: `SKILL.md`
- Test: `tests/test_docs_consistency.py`

**Interfaces:**
- Produces consistent user and skill docs for the new structure.

- [ ] **Step 1: Write failing docs test**

Create `tests/test_docs_consistency.py` with a test named
`test_docs_reference_workspace_and_commands`. It must read `README.md`,
`SKILL.md`, `docs/architecture.md`, `docs/workflow.md`, and
`docs/naming-conventions.md`, then assert all required strings are present:
`workspace/courses`, `mnemo-ingest`, `mnemo-generate`, `mnemo-audit`,
`mnemo-import`, `mnemo-export-note-types`, and `python scripts/ingest.py`.

Run: `pytest tests/test_docs_consistency.py -q`

Expected: FAIL until docs are updated.

- [ ] **Step 2: Add docs**

`docs/architecture.md` must describe each package namespace, `scripts/` as
compatibility wrappers only, and `workspace/` as the private course-first study
workspace.

`docs/workflow.md` must describe the flow: paste raw files into
`source-materials/`, create Cornell notes in `cornell-notes/`, generate drafts
into `cards/`, audit/approve, then import or export artifacts into `exports/`.

`docs/naming-conventions.md` must include examples for `bio-101`,
`01-cell-structure`, `2026-08-06-lecture-cell-structure.pdf`,
`2026-08-06-cell-structure.cornell.md`,
`2026-08-06-cell-structure.cards.csv`,
`2026-08-06-cell-structure.cards.jsonl`, and
`2026-08-06-cell-structure.apkg`.

Update `README.md` and `SKILL.md` to prefer `mnemo-*` commands while documenting compatibility commands.

- [ ] **Step 3: Verify and commit**

Run:

```bash
pytest tests/test_docs_consistency.py -q
git add README.md SKILL.md docs tests/test_docs_consistency.py
git commit -m "docs: document package and workspace workflow"
```

---

### Task 8: Full Verification

**Files:**
- Modify only files needed to fix verification failures.

**Interfaces:**
- Produces a verified branch ready for mandatory review.

- [ ] **Step 1: Search for stale imports**

Run:

```bash
rg -n "from scripts|import scripts|scripts\\.(adapter|anki_connect|audit_cards|calibrate|card_schema|config|genanki_export|generate_flashcards|import_cards|import_refined_csv|ingest|knowledge|media|note_types|verbatim)" src tests README.md SKILL.md docs
```

Expected: no stale package imports. Compatibility command examples may remain.

- [ ] **Step 2: Check file sizes**

Run:

```bash
wc -l src/mnemo/**/*.py scripts/*.py tests/*.py docs/*.md docs/superpowers/plans/*.md
```

Expected: no newly created or rewritten file exceeds 800 lines.

- [ ] **Step 3: Run full verification**

Run:

```bash
pytest
pytest --cov
python -m pip install -e .
mnemo-ingest --help
mnemo-generate --help
mnemo-audit --help
mnemo-import --help
mnemo-export-note-types --help
python scripts/ingest.py --help
python scripts/generate_flashcards.py --help
python scripts/audit_cards.py --help
python scripts/import_cards.py --help
python scripts/export_note_types.py --help
```

Expected: all commands pass and coverage is at or above 80%.

- [ ] **Step 4: Commit verification fixes**

If files changed:

```bash
git add <fixed-files>
git commit -m "fix: complete project restructure verification"
```

If no files changed, do not create an empty commit.

---

### Task 9: Mandatory Review Gate

**Files:**
- Review all changes after commit `c620cbd`.

**Interfaces:**
- Produces review findings and required fixes before merge.

- [ ] **Step 1: Generate review diff**

Run:

```bash
git diff c620cbd...HEAD --stat
git diff c620cbd...HEAD
```

- [ ] **Step 2: Review checklist**

Check:

```text
no hardcoded secrets
workspace private files ignored
tracked templates not ignored
wrappers contain no business logic
imports use mnemo.* package paths
tests cover package imports, wrappers, workspace ignore rules, and existing behavior
coverage remains at or above 80%
new or rewritten files stay under 800 lines
```

- [ ] **Step 3: Use code-reviewer and fix findings**

Ask code-reviewer to inspect `c620cbd...HEAD` for package import regressions, CLI wrapper behavior, `.gitignore` safety, package data loading, docs consistency, and missing tests.

Fix every CRITICAL and HIGH finding. Address MEDIUM findings when the fix is low-risk. Note remaining LOW findings in the final implementation summary.

- [ ] **Step 4: Re-run verification and commit fixes**

Run:

```bash
pytest
pytest --cov
mnemo-ingest --help
python scripts/ingest.py --help
```

If files changed:

```bash
git add <fixed-files>
git commit -m "fix: address restructure review findings"
```
