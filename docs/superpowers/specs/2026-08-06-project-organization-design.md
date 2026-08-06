# Mnemo Project Organization Design

## Purpose

Mnemo should be maintainable as both a Python toolkit and a Codex/Claude skill
while also being useful as a day-to-day study workspace. The project needs a
clear separation between tool source code, tracked templates, private course
materials, generated Cornell notes, card drafts, and Anki export artifacts.

## Goals

- Add a course-first workspace where real study materials can live locally
  without being committed.
- Add tracked templates for course folders, module folders, Cornell notes, and
  metadata.
- Establish a consistent naming convention for courses, modules, source
  materials, Cornell notes, generated card drafts, and exports.
- Restructure the Python code into an installable `src/mnemo/` package with
  clear responsibility boundaries.
- Preserve existing script-based workflows during migration through compatibility
  wrappers or documented transition commands.
- Keep the Codex/Claude skill usable throughout the restructure.

## Non-Goals

- Do not add a database or persistent service.
- Do not replace Anki as the review engine.
- Do not redesign the flashcard generation pedagogy.
- Do not import real course materials into git.
- Do not add speculative automation beyond the structure needed for the current
  workflow.

## Target Repository Structure

```text
src/mnemo/
  __init__.py
  cli/
  core/
  anki/
  pipeline/
  resources/

scripts/
  ingest.py
  generate_flashcards.py
  audit_cards.py
  import_cards.py
  export_note_types.py

workspace/
  README.md
  courses/
    _template/
      README.md
      course.yaml
      00-module-template/
        README.md
        module.yaml
        source-materials/
          .gitkeep
        cornell-notes/
          cornell-note.template.md
        cards/
          .gitkeep
        exports/
          .gitkeep

docs/
  architecture.md
  workflow.md
  naming-conventions.md
  roadmap.md
  superpowers/
    specs/
    plans/

tests/
```

The top-level repository remains the tool project. `workspace/` becomes the
user-facing study workspace. `src/mnemo/` becomes the package implementation.
`scripts/` remains temporarily as thin compatibility wrappers for documented
commands such as `python scripts/ingest.py`.

## Package Boundaries

`src/mnemo/core/` owns domain-neutral contracts and reusable logic:

- card schemas
- knowledge structures
- verbatim handling
- config loading
- validation primitives

`src/mnemo/anki/` owns Anki-specific integration:

- Fact-to-note adaptation
- AnkiConnect API calls
- `.apkg` export
- MONO note types
- media/font handling

`src/mnemo/pipeline/` owns workflow orchestration:

- source ingestion
- deterministic flashcard drafting
- audit reporting
- retention calibration
- refined CSV import

`src/mnemo/cli/` owns command-line entrypoints and argument parsing. CLI modules
should delegate quickly to `core`, `anki`, or `pipeline` modules.

## Command Strategy

Preferred commands should eventually be package entrypoints:

```text
mnemo-ingest
mnemo-generate
mnemo-audit
mnemo-import
mnemo-export-note-types
```

During migration, existing documented commands stay supported through thin
wrappers in `scripts/`:

```bash
python scripts/ingest.py <source>
python scripts/generate_flashcards.py notes.md --output cards/session.csv
python scripts/audit_cards.py cards/session.csv --settings cards/session.settings.json
python scripts/import_cards.py cards/session.jsonl
python scripts/export_note_types.py -o mnemo-note-types.apkg
```

Wrappers should contain no business logic. They should import and call the
matching package CLI function.

## Workspace Model

The workspace is course-first and module-nested:

```text
workspace/courses/<course-slug>/<module-slug>/
  source-materials/
  cornell-notes/
  cards/
  exports/
  module.yaml
```

Folder responsibilities:

- `source-materials/`: private raw inputs such as PDFs, slides, text, copied
  lectures, readings, and screenshots.
- `cornell-notes/`: private generated or edited Cornell-format notes derived
  from source materials.
- `cards/`: private generated CSV, JSONL, settings, coverage, manifest, and
  violation sidecars.
- `exports/`: private `.apkg` files and import artifacts.
- `course.yaml`: tracked course-level metadata template.
- `module.yaml`: tracked module-level metadata template.

## Git Tracking Policy

Templates and empty scaffolding are tracked. Real materials and generated study
outputs are ignored.

Tracked files under `workspace/`:

- `README.md`
- `.gitkeep`
- `course.yaml`
- `module.yaml`
- `*.template.md`

Ignored files under `workspace/`:

- real files in `source-materials/`
- real Cornell notes in `cornell-notes/`
- generated card artifacts in `cards/`
- Anki exports and import artifacts in `exports/`

The ignore rules must explicitly un-ignore tracked templates and metadata so the
folders remain visible in fresh clones.

## Naming Convention

Use lowercase ASCII slugs with hyphens. Avoid spaces in paths. Use numeric
module prefixes when sequence matters.

```text
course slug: bio-101
module slug: 01-cell-structure
source material: 2026-08-06-lecture-cell-structure.pdf
Cornell note: 2026-08-06-cell-structure.cornell.md
card draft: 2026-08-06-cell-structure.cards.csv
JSONL facts: 2026-08-06-cell-structure.cards.jsonl
Anki export: 2026-08-06-cell-structure.apkg
```

Dates use `YYYY-MM-DD`. File slugs should describe the learning unit, not the
tool action. Metadata files can carry human-readable titles, tags, source
status, and deck targets.

## Metadata

`course.yaml` should include:

```yaml
courseSlug: bio-101
courseTitle: Biology 101
term: 2026-fall
defaultDeck: Mnemo::Biology 101
tags:
  - biology
```

`module.yaml` should include:

```yaml
moduleSlug: 01-cell-structure
moduleTitle: Cell Structure
courseSlug: bio-101
sourceStatus: pending
noteStatus: pending
cardStatus: pending
tags:
  - cells
```

Status values should be simple strings such as `pending`, `drafted`,
`reviewed`, `approved`, `imported`, or `omitted`.

## Cornell Note Template

The tracked Cornell note template should be Markdown and should support:

- course/module metadata
- source references
- cues/questions
- notes
- summary
- follow-up gaps
- candidate card prompts

The template should guide Codex/Claude toward structured notes without forcing
the flashcard generator to parse every section immediately.

## Documentation

Add or update docs for:

- project architecture
- workspace workflow
- naming conventions
- migration notes from `scripts/` modules to `src/mnemo/`

`README.md` should stay concise and user-facing. Detailed workflow and
architecture details should live in `docs/`.

`SKILL.md` should continue to describe the skill workflow and supported
commands. It should not duplicate long reference material.

## Migration Phases

1. Add workspace scaffolding, templates, naming docs, and ignore rules.
2. Move implementation modules from `scripts/` into `src/mnemo/`.
3. Add thin wrappers in `scripts/` that preserve existing commands.
4. Update imports, tests, coverage config, and package metadata.
5. Add package console entrypoints.
6. Update `README.md`, `SKILL.md`, and docs to prefer the new package commands
   while documenting compatibility wrappers.
7. Run the full test suite with coverage.

## Testing Requirements

- Existing behavior must remain covered by the current test suite.
- Tests should be updated to import from `mnemo.*` package modules.
- Compatibility wrapper tests should verify that key `python scripts/*.py`
  commands still run.
- Add tests or assertions for workspace ignore behavior where practical.
- Coverage must remain at or above 80%.

## Risks

- Import path migration can cause broad test failures if done in one large edit.
- Wrapper commands can drift if business logic remains in `scripts/`.
- Overly broad `.gitignore` rules can accidentally hide templates or metadata.
- Docs can become inconsistent if `README.md`, `SKILL.md`, and CLI entrypoints
  are not updated together.

## Implementation Decisions

- Use the console entrypoint names listed in the Command Strategy section:
  `mnemo-ingest`, `mnemo-generate`, `mnemo-audit`, `mnemo-import`, and
  `mnemo-export-note-types`.
- Use `importlib.resources` for package-owned resources such as bundled fonts
  once those resources move under `src/mnemo/resources/`.
- Keep existing path-based behavior only inside temporary compatibility wrappers
  where needed to preserve `python scripts/*.py` commands during migration.
