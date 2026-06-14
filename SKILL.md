---
name: mnemo
description: Generate, audit, and import atomic recall-first Anki flashcards from Markdown, plain text, pasted notes, Q&A pairs, PDFs, or lecture slides. Use when Codex needs to turn study material into Anki cards, enforce card-quality and workload rules, create mixed card formats, validate an existing CSV deck, or analyze mature-card retention.
---

# Mnemo

Create understandable, atomic flashcards and verify them before import. Keep
semantic decisions reviewable; use deterministic scripts for parsing, validation,
interleaving, export, and import.

## Required Reading

Read [references/anki_best_practices.md](references/anki_best_practices.md) before
changing generation rules, scheduler settings, or evidence claims. It distinguishes
research findings from Mnemo policy and documents the FSRS/legacy-SM-2 boundary.

## Workflow

1. Identify the source, deck, topics, and expected prerequisite knowledge.
2. Ingest Markdown or text directly. For PDF/PPTX, run
   `python scripts/ingest.py <source>` and preserve page/slide provenance.
3. Ensure the source teaches each fact before testing it. Defer unsupported facts.
4. Add at least one relevant source image. Use Markdown image syntax or:

   ```text
   [image: https://example.org/diagram.png | alt: This diagram cues the spatial relationship tested by the card.]
   ```

5. Generate an audited CSV:

   ```bash
   python scripts/generate_flashcards.py notes.md --output cards/session.csv
   ```

6. Run the independent rubric audit:

   ```bash
   python scripts/test_card_quality.py cards/session.csv \
     --settings cards/session.settings.json
   ```

7. Review every error and warning against the source. Heuristics can detect likely
   compounds but cannot prove semantic atomicity.
8. Show the draft and report to the user. Require approval before import.
9. Import the CSV into an Anki note type with matching fields, or use the existing
   Fact JSONL/AnkiConnect pipeline when direct configured import is required.
10. Report generated, rejected, duplicate, and imported counts.

## Input Forms

Accept mixed Markdown and plain text:

```markdown
# Biology
Q: What organelle produces most cellular ATP?
A: The mitochondrion.
Extra: Oxidative phosphorylation occurs across the inner mitochondrial membrane.
Tags: biology cell-respiration

ATP synthase uses a proton gradient to produce ATP.

![A labeled mitochondrion whose inner membrane cues ATP production](mitochondrion.png)
The cristae increase inner-membrane surface area.
```

Also accept `question :: answer`, tab-separated pairs, bullets, headings, and raw
prose. Treat headings and `Topic:` lines as interleaving topics.

## Required Card Contract

The generated CSV contains these required Anki fields:

- `Front`
- `Back`
- `Extra`
- `Mnemonic`
- `CardType`
- `Tags`

It also includes `ImageURL`, `ImageAlt`, `Topic`, `Source`, and `CardID` for
validation and traceability.

Use only these card types:

- `qa`: direct active-recall question and short answer
- `cloze`: one meaningful deletion in context
- `reverse`: reverse direction only when the relation is genuinely reversible
- `image-supported`: a recall prompt paired with a relevant explanatory visual

Do not create multiple-choice cards, passive summary cards, decorative images, or
custom in-card JavaScript.

## Generation Rules

Apply all rules:

1. Test one independently gradable fact per card.
2. Split detectable sentence boundaries, independent clauses, and enumerations.
3. Keep `Front` below 20 words. Shorten or split anything longer.
4. Keep estimated working-memory load at four components or fewer.
5. Add an acronym or visual association when a source concept has at least three
   components, even after its components become separate cards.
6. Begin `Extra` with `Explanation:` and include enough explanation to support
   understanding before memorization.
7. Add `Context:` when prerequisite domain knowledge may be required.
8. Require image alt text to explain what the visual cues and why it aids recall.
9. Produce at least three card types per deck when at least three atomic facts exist.
   Do not duplicate a fact solely to meet the format quota.
10. Interleave topics automatically; avoid adjacent cards from the same topic when
    another topic remains available.
11. Preserve source provenance and stable card IDs.

## Scheduler Policy

Default to the requested legacy profile:

```text
scheduler: legacy-sm2
learning steps: 10m 1d
graduating interval: 3d
easy interval: 7d
starting/max ease: 250%
new cards/day: 20 maximum
Easy policy: avoid
```

Allow command-line overrides, but log deviations. Never allow `max_ease_percent`
above 250 or `new_cards_per_day` above 20 in a passing report.

Do not describe this profile as universally optimal. With `--scheduler fsrs`, reject
learning steps of one day or longer. CSV cannot disable Anki's Easy button; record
`easy_button_policy=avoid` as user guidance and state that portable enforcement is
false in the settings sidecar.

## Validation Gate

Treat these as blocking errors:

- missing Front, Back, or explanation
- Front over 19 words
- estimated answer load over four components
- missing mnemonic for three or more components
- fewer than three card types in a sufficiently large deck
- no relevant image-supported card
- image without explanatory alt text
- new-card limit above 20
- ease cap above 250%
- FSRS with a day-or-longer learning step

Treat likely compound facts and avoidable same-topic runs as warnings requiring
review. Do not silently discard violations. Write them to
`<deck>.violations.json` and return a nonzero exit status when errors remain.

## Retention Hook

For review data, accept a CSV with:

```csv
card_id,interval_days,predicted_retention,actual_recalled
abc123,30,0.90,1
def456,45,0.90,0
```

Run:

```bash
python scripts/test_card_quality.py cards/session.csv \
  --settings cards/session.settings.json \
  --retention-log reviews.csv
```

Compare predicted and actual recall only for mature reviews with intervals greater
than 21 days. Report per-review calibration error and mean calibration error. Do
not claim a retention model was validated when no mature review rows exist.

## Import Notes

The generator emits notes plus a scheduler sidecar; Anki CSV import does not apply
deck options. Apply the sidecar to the target preset manually or through a separate
AnkiConnect preset workflow.

For the repository's existing direct-import path, continue to use approved Fact
JSONL with `python scripts/import_cards.py cards/session.jsonl`. Its `.apkg`
fallback and native image-occlusion limitations remain unchanged.

## Skill Architecture

Keep only `name` and `description` in YAML frontmatter for Codex skill triggering.
Keep workflow and invariants in this file. Keep research detail and citations in
`references/`. Keep deterministic operations in `scripts/`. Keep reusable output
resources in `assets/` only when an actual template or media asset is required.
Do not duplicate reference prose in this file.
