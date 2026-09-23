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
