# Workspace Workflow

Start in `workspace/courses` by copying the course and module templates, then
update their metadata. Each module follows the same private study workflow.

1. Paste raw PDFs, slides, text, and other source files into `source-materials/`.
2. Create source-grounded Cornell notes in `cornell-notes/`. Use
   `mnemo-cornell` for a deterministic first draft from normalized text.
3. Generate card drafts into `cards/` with `mnemo-generate`; `.cornell.md`
   inputs generate only from `## Candidate Cards` by default. Use
   `mnemo-ingest` first when source normalization is needed.
4. Run `mnemo-audit`, review the draft against the source, and approve it before
   importing.
5. Use `mnemo-import` for approved cards or `mnemo-export-note-types` for note
   type packages; keep exported artifacts in `exports/`.

Treat `## Cues`, `## Notes`, and `## Summary` as study context. Treat
`## Candidate Cards` as the explicit human-review contract consumed by
`mnemo-generate`.

The legacy script commands remain available as compatibility wrappers, including
`python scripts/ingest.py <source>`. See [Architecture](architecture.md) for the
command boundary and [Naming conventions](naming-conventions.md) for paths.
