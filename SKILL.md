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
mnemo ingest <source> [--ocr] [--lang eng] [--extract-images DIR]
mnemo draft <source> --deck DECK -o deck.mnemo.yaml [--directions MODE] [--ocr] [--lang eng] [--deferred deferred.md]
mnemo audit deck.mnemo.yaml
mnemo import deck.mnemo.yaml [--config config.toml] [--apkg-out deck.apkg] [--update-existing]
mnemo export-note-types [--config config.toml]
```

`--deck` is required when drafting and supplies the deck name stored in the
manifest. `--directions` accepts `term-to-definition` (the default),
`definition-to-term`, or `both`. Mnemo reads and writes `.mnemo.yaml` deck
manifests; CSV input and CSV export are intentionally unsupported.

Supported source formats: Markdown/plain text (`.md`, `.txt`), PDF, PPTX,
DOCX. Web pages are ingested by URL through `mnemo.ingest.web.ingest_web()`
rather than through `mnemo ingest` (no file path).

`--lang` is a Tesseract language code, default `eng`. Use `fil` for
Filipino/Tagalog (Tesseract's code is `fil`, not `tgl`), or `eng+fil` for
scanned pages mixing English and Filipino text. Only affects `--ocr`.
Requires the matching `tesseract-langpack-<code>` installed on the system
(e.g. `sudo dnf install tesseract tesseract-langpack-fil` on Fedora).

## Workflow

Mnemo divides labor by what each layer does best. Deterministic code ingests
and **drafts** only what it can confidently ground; the agent (you)
**authors** the rest. The drafter never invents a prompt it cannot ground —
prose it cannot parse is left in `deferred.md` for you to author. Do not
treat the generated YAML manifest as a finished deck.

1. Identify the source, deck, and expected prerequisite knowledge.

2. **Ingest (deterministic).** MD/text is read directly. For PDF/PPTX/DOCX,
   `mnemo ingest <source>` prints normalized chunks with provenance
   (`file.pdf p.4`, `deck.pptx slide 3`, `file.docx`). PDF image-only pages
   are surfaced as a visible marker instead of being dropped; add `--ocr`
   (and `--lang` for non-English scans) to recover their text through
   Tesseract when available (tagged `(OCR)` in provenance as lower
   confidence). Detected PDF tables are re-emitted as
   `header | value` rows; PPTX charts are re-emitted as category/series/value
   tables. Add `--extract-images DIR` to save qualifying source visuals.

3. **Draft (deterministic).** Run

   ```bash
   mnemo draft notes.md --deck "Mnemo::Course::Module" -o module.mnemo.yaml
   ```

   This grounds only what it can confidently pattern-match: explicit `Q:`/`A:`
   blocks, `question :: answer` pairs, tab-separated pairs, `Term: definition`
   lines, and a bulleted list under a clear stem line. Everything else is
   written to `<cards>.deferred.md` with the source excerpt and a reason —
   never guessed at. The YAML manifest is a draft.

4. **Author deferred units and strengthen weak drafts (you).** This is the
   step deterministic code cannot do. For every unit in `deferred.md`, and
   every card the audit flags (`ATOMICITY_REVIEW`, `THIN_EXPLANATION`,
   `GENERIC_PROMPT`), write or rewrite the card directly in the YAML manifest following
   the Required Card Contract and Generation Rules below. Turn prose into one
   atomic, specifically phrased prompt whose `extra` explains *why* the fact
   holds. Leave genuinely unsupported units deferred — never fabricate a
   prompt to clear a warning.

5. Add a source image only when it teaches visual or spatial knowledge, in
   the card's `image` field using Markdown image syntax.

6. **Audit (deterministic).** Run the independent rubric audit:

   ```bash
   mnemo audit module.mnemo.yaml
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
   mnemo import module.mnemo.yaml
   ```

   Tries AnkiConnect first (Anki desktop must be running with the
   AnkiConnect add-on, code 2055492159); falls back to writing a `.apkg`
   file you import by hand (File → Import in Anki) when AnkiConnect isn't
   reachable. Skipped cards (usually AnkiConnect-detected duplicates) are
   printed individually — never silently dropped.

   When applying an edited manifest to notes already in Anki, use
   `mnemo import --update-existing module.mnemo.yaml` after approval. It
   matches the exact stored `CardID` (including case), updates matched
   notes' fields in place, and adds cards with unmatched IDs. Ambiguous
   IDs or a note-type mismatch stop the import before any note is written.
   The regular import is add-only. If AnkiConnect is unavailable, update
   mode exports an offline `.apkg` instead; importing that package is not
   an in-place update.

10. Report generated, authored, deferred, skipped, and imported counts.

## Required Card Contract

Each `.mnemo.yaml` manifest has this shape:

```yaml
formatVersion: 1
deck:
  name: "Mnemo::Course::Module"
  tags: [course]
cards:
  - id: course-module-atp
    front: "What does ATP stand for?"
    back: "Adenosine triphosphate."
    cardType: qa
    tags: [energy]
```

`formatVersion: 1`, a non-empty `deck.name`, and a `cards` list are required.
Each card requires a non-empty `id`, `front`, and `back`; IDs must be unique
within the manifest. `deck.tags` and card `tags` are optional lists of
single-word tags, not comma-separated strings. `cardType` is optional and
defaults to `qa`. Optional card fields are `extra`, `mnemonic`, `image`,
`topic`, `source`, and `confidence` (a number from 0 to 1). Use the YAML keys
shown here: `cardType` and `id`, not internal Python names.

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
3. Keep `front` at most 150 characters. Shorten or split anything longer.
   (Character length, not word count -- particle-heavy languages like
   Tagalog need more words for the same complexity an English sentence
   expresses more densely.)
4. Keep estimated working-memory load at four components or fewer.
5. Choose card format from the knowledge structure. Never manufacture variety.
6. Add an acronym or visual association when a source concept has at least
   three components, even after its components become separate cards.
7. Begin `extra` with `Explanation:` and include enough explanation to
   support understanding before memorization.
8. Preserve qualifications, exceptions, units, formula domains, uncertainty,
   and competing interpretations.
9. Interleave topics; avoid adjacent cards from the same topic when another
   topic is available.
10. Preserve source provenance (`source`) and a stable `id` when possible.
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
