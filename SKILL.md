---
name: mnemo
description: Generate, audit, and import source-grounded, recall-first Anki study decks from Markdown, text, PDFs, lecture slides, DOCX, or web pages. Use when Claude needs to create concise cards for facts, comparisons, processes, formulas, or enumerations, validate card quality, or import a deck into Anki.
---

# Mnemo

Create understandable, independently gradable flashcards and verify them before
import. Preserve essential context while keeping recall atomic.

## Commands

One installed command, `mnemo`, with subcommands for each pipeline stage:

```bash
mnemo ingest <source> [--ocr] [--extract-images DIR]
mnemo draft <source> -o cards.csv [--deferred deferred.md]
mnemo audit cards.csv
mnemo import cards.csv --deck DECK [--config config.toml] [--apkg-out deck.apkg]
mnemo export-note-types [--config config.toml]
```

Supported source formats: Markdown/plain text (`.md`, `.txt`), PDF, PPTX,
DOCX. Web pages are ingested by URL through `mnemo.ingest.web.ingest_web()`
rather than through `mnemo ingest` (no file path).

## Workflow

Mnemo divides labor by what each layer does best. Deterministic code ingests
and **drafts** only what it can confidently ground; the agent (you)
**authors** the rest. The drafter never invents a prompt it cannot ground —
prose it cannot parse is left in `deferred.md` for you to author. Do not
treat the generated CSV as a finished deck.

1. Identify the source, deck, and expected prerequisite knowledge.

2. **Ingest (deterministic).** MD/text is read directly. For PDF/PPTX/DOCX,
   `mnemo ingest <source>` prints normalized chunks with provenance
   (`file.pdf p.4`, `deck.pptx slide 3`, `file.docx`). PDF image-only pages
   are surfaced as a visible marker instead of being dropped; add `--ocr` to
   recover their text through Tesseract when available (tagged `(OCR)` in
   provenance as lower confidence). Detected PDF tables are re-emitted as
   `header | value` rows; PPTX charts are re-emitted as category/series/value
   tables. Add `--extract-images DIR` to save qualifying source visuals.

3. **Draft (deterministic).** Run

   ```bash
   mnemo draft notes.md -o cards.csv
   ```

   This grounds only what it can confidently pattern-match: explicit `Q:`/`A:`
   blocks, `question :: answer` pairs, tab-separated pairs, `Term: definition`
   lines, and a bulleted list under a clear stem line. Everything else is
   written to `<cards>.deferred.md` with the source excerpt and a reason —
   never guessed at. The CSV is a draft.

4. **Author deferred units and strengthen weak drafts (you).** This is the
   step deterministic code cannot do. For every unit in `deferred.md`, and
   every card the audit flags (`ATOMICITY_REVIEW`, `THIN_EXPLANATION`,
   `GENERIC_PROMPT`), write or rewrite the card directly in the CSV following
   the Required Card Contract and Generation Rules below. Turn prose into one
   atomic, specifically phrased prompt whose `Extra` explains *why* the fact
   holds. Leave genuinely unsupported units deferred — never fabricate a
   prompt to clear a warning.

5. Add a source image only when it teaches visual or spatial knowledge, via
   Markdown image syntax or the `Image` CSV column.

6. **Audit (deterministic).** Run the independent rubric audit:

   ```bash
   mnemo audit cards.csv
   ```

   Errors block import; warnings require review against the source.
   Heuristics can flag likely compounds and thin explanations but cannot
   prove semantic atomicity — judge each case.

7. Loop steps 4–6 until no errors remain and every warning is resolved or
   consciously accepted with a reason.

8. Show the draft, the deferred units, and the audit summary. Require
   approval before import.

9. **Import.**

   ```bash
   mnemo import cards.csv --deck "Mnemo::Course::Module"
   ```

   Tries AnkiConnect first (Anki desktop must be running with the
   AnkiConnect add-on, code 2055492159); falls back to writing a `.apkg`
   file you import by hand (File → Import in Anki) when AnkiConnect isn't
   reachable. Skipped cards (usually AnkiConnect-detected duplicates) are
   printed individually — never silently dropped.

10. Report generated, authored, deferred, skipped, and imported counts.

## Required Card Contract

The `cards.csv` contains these fields (header row):

```
Front,Back,Extra,Mnemonic,CardType,Tags,Image,Topic,Source,CardID,Confidence
```

- `Front`, `Back`, `CardType` are required and non-empty.
- `Extra`, `Mnemonic`, `Tags` may be blank but should be filled in during
  authoring (step 4) per the Generation Rules.
- `Image`, `Topic`, `Source`, `CardID`, `Confidence` are optional
  traceability/validation fields.

Use only these card types:

- `qa`: direct active-recall question and short answer
- `cloze`: one meaningful deletion in context (`{{c1::answer}}`)
- `reverse`: reverse direction only when the relation is genuinely reversible
- `typed`: exact notation, formulas, dates, symbols, or short canonical answers
- `list`: a meaningful set or ordered sequence, rendered as cloze deletions
- `image-supported`: a recall prompt paired with a relevant explanatory visual

Do not create multiple-choice cards, passive summary cards, decorative
images, or custom in-card JavaScript.

## Generation Rules

These bind the agent when authoring or rewriting cards (step 4):

1. Test one independently gradable fact per card.
2. Split detectable sentence boundaries, independent clauses, and enumerations.
3. Keep `Front` below 150 characters. Shorten or split anything longer.
   (Character length, not word count -- particle-heavy languages like
   Tagalog need more words for the same complexity an English sentence
   expresses more densely.)
4. Keep estimated working-memory load at four components or fewer.
5. Choose card format from the knowledge structure. Never manufacture variety.
6. Add an acronym or visual association when a source concept has at least
   three components, even after its components become separate cards.
7. Begin `Extra` with `Explanation:` and include enough explanation to
   support understanding before memorization.
8. Preserve qualifications, exceptions, units, formula domains, uncertainty,
   and competing interpretations.
9. Interleave topics; avoid adjacent cards from the same topic when another
   topic is available.
10. Preserve source provenance (`Source`) and a stable `CardID` when possible.
11. Do not import until every deferred unit is authored, deferred with a
    reason, or intentionally omitted, and the user has approved the draft.

## Scheduler Policy

Default to FSRS, Anki's current recommended scheduler:

```text
scheduler: fsrs
desired_retention: 0.9
new_cards/day maximum: 20
```

Configurable via `config.toml` (see `config.example.toml`); overrides are
applied at deck-config level when importing via AnkiConnect.

## Study Workspace

`workspace/` is the private, course-first study workspace. Create courses
under `workspace/courses` from the tracked template in
`workspace/courses/_template`. Real study files (source materials, generated
cards) stay local and gitignored; templates and metadata are tracked.
