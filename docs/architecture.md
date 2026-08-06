# Architecture

Mnemo is an installable Python package under `src/mnemo/`, with a private
course-first study workspace under `workspace/`.

## Package Namespaces

- `mnemo.core`: domain-neutral contracts and reusable logic, including card
  schemas, knowledge structures, configuration, validation, and verbatim
  handling.
- `mnemo.anki`: Anki-specific adapters, AnkiConnect integration, note types,
  media and font handling, and `.apkg` export.
- `mnemo.pipeline`: source ingestion, card drafting, auditing, calibration, and
  import/export workflow orchestration.
- `mnemo.cli`: command-line entry points that parse arguments and delegate to
  the package layers.
- `mnemo.resources`: package-owned files, including bundled fonts in
  `src/mnemo/resources/fonts`.

## Commands and Compatibility

The installed entry points are `mnemo-ingest`, `mnemo-generate`, `mnemo-audit`,
`mnemo-import`, and `mnemo-export-note-types`. The `scripts/` directory contains
compatibility wrappers only; it contains no business logic. Existing invocations,
including `python scripts/ingest.py <source>`, remain supported during migration.

## Study Workspace

`workspace/` is the private, course-first study workspace. Create courses under
`workspace/courses` from the tracked templates. Each module keeps private raw
materials, Cornell notes, card drafts, and exports in its own folders. Templates
and metadata are tracked; real study files and generated artifacts stay local.
