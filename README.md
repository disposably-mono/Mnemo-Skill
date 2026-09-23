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
mnemo draft notes.md -o cards.csv         # deterministic draft + deferred.md
# ... author deferred units and weak cards directly in cards.csv ...
mnemo audit cards.csv                     # rubric validation
mnemo import cards.csv --deck "Mnemo::Course::Module"
```

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
