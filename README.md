# Mnemo

A Claude Code skill and Python toolkit that turns study material into
source-grounded, recall-first Anki flashcards and imports them via
AnkiConnect (with an offline `.apkg` fallback).

Recall-first design only: cloze, basic QA, and typed-answer cards. No
multiple-choice, no decorative images, no in-card JavaScript.

## Install

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Usage

```bash
mnemo ingest notes.pdf --ocr              # normalize a source into text chunks
mnemo draft notes.md --deck "Mnemo::Course::Module" -o module.mnemo.yaml
# ... author deferred units and weak cards in module.mnemo.yaml ...
mnemo audit module.mnemo.yaml             # rubric validation
mnemo import module.mnemo.yaml
```

Deck names are required when drafting and are stored in the manifest. Draft
directions are `term-to-definition` (default), `definition-to-term`, or
`both`, selected with `--directions`. Decks use YAML manifests only: CSV input
and CSV export are intentionally unsupported.

To apply edits to a deck already in Anki while keeping existing note and card
IDs, use `mnemo import --update-existing module.mnemo.yaml`. This opt-in mode
matches notes by the exact, case-sensitive `CardID` stored in Anki, updates
only their fields in place, and adds cards whose IDs have no exact match.
Ambiguous IDs or a matching note with the wrong note type stop the import
before any note is written. The regular import remains add-only. If
AnkiConnect is unavailable, either command exports an offline `.apkg` file;
the offline export does not update notes in place.

See [SKILL.md](SKILL.md) for the full agent-facing workflow, card contract,
and generation rules.

## Development

```bash
.venv/bin/pytest -q --cov=mnemo --cov-report=term
```

80% minimum coverage is enforced (`[tool.coverage.report] fail_under = 80` in
`pyproject.toml`).

## License

MIT, see [LICENSE](LICENSE). Bundled fonts (DM Mono, DM Serif Display,
Outfit) carry their own licenses under `src/mnemo/resources/fonts/`.
