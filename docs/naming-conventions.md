# Naming Conventions

Use lowercase ASCII slugs with hyphens and no spaces. Use numeric module
prefixes when order matters, and use ISO dates (`YYYY-MM-DD`) at the beginning
of generated file names.

| Item | Example |
| --- | --- |
| Course slug | `bio-101` |
| Module slug | `01-cell-structure` |
| Source material | `2026-08-06-lecture-cell-structure.pdf` |
| Cornell note | `2026-08-06-cell-structure.cornell.md` |
| Card draft | `2026-08-06-cell-structure.cards.csv` |
| JSONL facts | `2026-08-06-cell-structure.cards.jsonl` |
| Anki export | `2026-08-06-cell-structure.apkg` |

Place course folders under `workspace/courses/<course-slug>/` and module folders
under `<module-slug>/`. Source file slugs should describe the learning unit, not
the command that produced the file.

Use the preferred commands `mnemo-ingest`, `mnemo-cornell`, `mnemo-generate`,
`mnemo-audit`, `mnemo-ready`, `mnemo-import`, and `mnemo-export-note-types`.
Compatibility commands remain documented, including `python scripts/ingest.py
<source>`.
