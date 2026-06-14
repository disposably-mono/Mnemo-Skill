---
name: mnemo
description: Generate, audit, and import source-grounded, recall-first Anki study decks from Markdown, text, Q&A, PDFs, or lecture slides. Use when Codex needs to model learning objectives and knowledge structures, create concise cards for facts, comparisons, processes, arguments, narratives, formulas, examples, exceptions, diagrams, or applications, validate coverage and card quality, or analyze mature-card retention.
---

# Mnemo

Create understandable, independently gradable flashcards and verify them before
import. Preserve essential context while keeping recall atomic. Plan what the
source teaches before deciding how to test it.

## Required Reading

Read [references/anki_best_practices.md](references/anki_best_practices.md) before
changing generation rules, scheduler settings, or evidence claims. It distinguishes
research findings from Mnemo policy and documents the FSRS/legacy-SM-2 boundary.
Read [references/knowledge_structures.md](references/knowledge_structures.md) when
authoring comparisons, processes, arguments, narratives, quantitative material,
examples, exceptions, procedures, or enrichment.

## Workflow

1. Identify the source, deck, topics, and expected prerequisite knowledge.
2. Ingest Markdown or text directly. For PDF/PPTX, run
   `python scripts/ingest.py <source>` and preserve page/slide provenance.
3. Extract explicit learning objectives. Infer one major-concept objective per
   topic only when objectives are absent.
4. Build knowledge units and classify their structure before authoring cards.
5. Ensure the source supports every assessed claim. Defer ambiguous or unsupported
   units. Label generated examples and practice as `Enrichment:`.
6. Add a source image only when it teaches visual or spatial knowledge. Use
   Markdown image syntax or:

   ```text
   [image: https://example.org/diagram.png | alt: This diagram cues the spatial relationship tested by the card.]
   ```

7. Generate an audited CSV plus semantic sidecars:

   ```bash
   python scripts/generate_flashcards.py notes.md --output cards/session.csv
   ```

   Review `<deck>.manifest.json` and `<deck>.coverage.json` for represented,
   deferred, unsupported, and omitted material.

8. Run the independent rubric audit:

   ```bash
   python scripts/test_card_quality.py cards/session.csv \
     --settings cards/session.settings.json
   ```

9. Review every error and warning against the source. Heuristics can detect likely
   compounds but cannot prove semantic atomicity.
10. Show the draft, unresolved units, and coverage report. Require approval before
    import.
11. Import the CSV into an Anki note type with matching fields, or use the existing
   Fact JSONL/AnkiConnect pipeline when direct configured import is required.
12. Report generated, deferred, rejected, duplicate, and imported counts.

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

It also includes image, topic, source, stable ID, knowledge-unit, objective,
prerequisite, origin, purpose, and confidence fields for validation and
traceability. The semantic `Fact` JSONL contract accepts the same metadata as
optional fields, so existing files remain valid.

Use only these card types:

- `qa`: direct active-recall question and short answer
- `cloze`: one meaningful deletion in context
- `reverse`: reverse direction only when the relation is genuinely reversible
- `typed`: exact notation, formulas, dates, symbols, or short canonical answers
- `list`: a meaningful set or ordered sequence whose order semantics are preserved
- `image-supported`: a recall prompt paired with a relevant explanatory visual

Do not create multiple-choice cards, passive summary cards, decorative images, or
custom in-card JavaScript.

## Generation Rules

Apply all rules:

1. Test one independently gradable fact per card.
2. Split detectable sentence boundaries, independent clauses, and enumerations.
3. Keep `Front` below 20 words. Shorten or split anything longer.
4. Keep estimated working-memory load at four components or fewer.
5. Choose card format from the knowledge structure. Never manufacture variety.
6. Add an acronym or visual association when a source concept has at least three
   components, even after its components become separate cards.
7. Begin `Extra` with `Explanation:` and include enough explanation to support
   understanding before memorization.
8. Add `Context:` when prerequisite domain knowledge may be required.
9. Require image alt text to explain what the visual cues and why it aids recall.
10. Preserve qualifications, exceptions, units, formula domains, theorem
    conditions, uncertainty, and competing interpretations.
11. Interleave topics automatically; avoid adjacent cards from the same topic when
    another topic remains available.
12. Preserve source provenance and stable card and knowledge-unit IDs.
13. Do not import until each objective is covered, deferred, unsupported, or
    intentionally omitted and the user has approved the draft.

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
- image without explanatory alt text
- missing source provenance
- unlabeled generated enrichment
- invalid semantic origin, confidence, knowledge kind, or learning purpose
- new-card limit above 20
- ease cap above 250%
- FSRS with a day-or-longer learning step

Treat likely compound facts, inferred claims, and avoidable same-topic runs as
warnings requiring review. Text-only and naturally single-format decks may pass.
Do not silently discard violations. Write them to
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
