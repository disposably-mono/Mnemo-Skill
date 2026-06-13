---
name: mnemo
description: Turn study material (Markdown, PDFs, lecture slides, pasted notes) into high-quality Anki flashcards and import them via AnkiConnect. Use when the user wants to make Anki cards, study for a class/exam, or convert notes/lectures into spaced-repetition cards.
---

# Mnemo: authoring high-quality Anki cards

Turn the user's study material into **atomic, recall-first Anki cards** and import
them into Anki. You are the intelligent middle of the pipeline: you read
the material and produce well-formed **Facts**; deterministic Python scripts handle
parsing and the Anki import.

**Never invent multiple-choice cards or custom in-card JavaScript.** Cards are
recall-first (cloze / basic / overlapping-cloze lists / typed answers / native
image occlusion). Distractors, when useful, are shown on the *answer* side as
"common confusions" — they are study aids, not clickable options.

## Workflow

Work through these steps. Use a TodoWrite list to track them for larger inputs.

1. **Scope it.** Identify the source (file path(s) or pasted text), the course, and
   the topic. These become the deck (`Course::Topic`) and tags
   (`course-slug`, `lecture-N`, `auto`).
2. **Ingest.** For Markdown / plain text / pasted notes, read directly. For PDF or
   PPTX, run `python scripts/ingest.py <file>` to get normalized text with page/slide
   provenance.
3. **Generate Facts.** Apply the card-quality rules below. Emit Facts conforming to
   `scripts/card_schema.py`. Write both a human-editable
   `cards/<session>.md` and a machine `cards/<session>.jsonl`. Read
   `config.toml` when present: omit `deck` only when its `default_deck` should
   apply, and do not duplicate its `auto_tag` manually.
4. **Review gate (REQUIRED).** Show the draft cards and ask the user to edit/approve
   `cards/<session>.md`. **Nothing is imported until they approve.** Re-read the file
   after they edit so their changes are honored.
5. **Import.** Run `python scripts/import_cards.py cards/<session>.jsonl`. It maps each
   Fact to the configured target note type (`config.toml` + `mappings.toml`), pushes to Anki
   via AnkiConnect, and falls back to a `.apkg` export if Anki isn't running.
6. **Confirm.** Report how many cards were added, skipped (duplicates), or failed, and
   whether an AnkiWeb sync was triggered.

## The Fact schema

A Fact is note-type-agnostic. Pick the `type` that fits the knowledge:

```jsonc
{
  "type": "qa" | "cloze" | "list" | "typed" | "image_occlusion",
  "content": { /* see per-type below */ },
  "distractors": [ { "text": "...", "grade": "near|medium|far" } ], // qa/cloze only, optional
  "deck": "Biology::Lecture 3",
  "tags": ["biology", "lecture-3", "auto"],
  "source": "lecture3.pdf p.4"
}
```

Content by type:
- **qa** → `{ "front": "...", "back": "..." }` — a single question and a short answer.
- **cloze** → `{ "text": "... {{c1::answer}} ...", "extra": "optional note" }` — fill in
  the blank(s); use `{{c1::}}`, `{{c2::}}` for multiple blanks in one sentence.
- **list** → `{ "title": "...", "items": ["...", "..."], "extra": "optional" }` — an
  enumeration or sequence (≥2 items). Becomes an overlapping-cloze set.
- **typed** → `{ "prompt": "...", "answer": "...", "hints": ["..."],
  "extra": "optional" }` — exact recall with zero to three progressively more
  revealing hints. Use only when exact spelling, notation, or syntax matters.
- **image_occlusion** → `{ "image": "diagram.png", "masks": [...],
  "header": "optional", "back_extra": "optional", "comments": "optional",
  "occlude_inactive": true }` — native Anki image occlusion. Image paths are
  resolved relative to the JSONL file. Each mask uses normalized 0–1 values.
  Add the same positive `card` number to multiple masks to group them onto one
  card:

  ```json
  {"shape":"rect", "left":0.1, "top":0.2, "width":0.3, "height":0.1, "card":1}
  {"shape":"ellipse", "left":0.5, "top":0.3, "rx":0.1, "ry":0.08}
  {"shape":"polygon", "left":0, "top":0, "points":[[0.1,0.2],[0.3,0.2],[0.2,0.4]]}
  ```

  Native image occlusion requires Anki 23.10+ with AnkiConnect reachable; it
  cannot use the `.apkg` fallback.

## Card-quality rules (SuperMemo's "20 rules", distilled)

1. **Atomic — one idea per card.** If an answer has multiple parts, split it.
2. **Minimum information principle.** Keep answers short and specific. Short cards are
   recalled faster and scheduled better.
3. **Prefer cloze for facts-in-context.** A fact embedded in a meaningful sentence is
   easier to recall than a bare Q→A.
4. **Never cram an enumeration into one card.** Lists/sequences → a `list` Fact, not a
   single card that asks "name all N".
5. **Be precise and unambiguous.** The front must have exactly one correct answer the
   user can produce from memory.
6. **Keep context/provenance.** Set `source` so cards are traceable to the material.
7. **Math/science:** wrap LaTeX in `\(...\)` (inline) or `\[...\]` (block) for MathJax.
8. **Don't make cards from material the user clearly doesn't understand yet** — flag it
   instead of generating noise.
9. **Use typed answers selectively.** Exact-input grading is appropriate for formulas,
   vocabulary spelling, commands, and notation, not ordinary conceptual answers.
10. **Use image occlusion only when spatial location matters.** Keep masks tight and
    avoid hiding large regions that test several labels at once.

## Distractor-grading rubric

For `qa` / `cloze` facts where confusing alternatives exist, optionally add 3–5
distractors so the answer side teaches the discriminations. Grade each by closeness:

- **near** — very plausible; commonly confused with the answer (the valuable ones).
- **medium** — related but distinguishable on reflection.
- **far** — clearly wrong, but topically adjacent (sanity anchors).

Aim for a spread weighted toward `near`. Distractors render answer-side only, grouped by
grade. Do **not** add distractors to `list` facts.

## List / enumeration handling

When the material is an ordered sequence (steps of a process, stages, a timeline) or an
unordered set (the N causes of X, members of a group), emit a single `list` Fact. The
importer turns it into an overlapping-cloze set: a chain of cards where each hides one
item while showing its neighbors as context — the robust, cross-platform way to memorize
lists without fragile add-ons.

## Guardrails

- Recall-first only: no MCQ note types or custom in-card JS.
- Always go through the review gate before importing.
- Default note types are the bundled MONO types; respect target overrides in
  `config.toml` and their field mappings in `mappings.toml`.
- If AnkiConnect is unreachable, the importer writes a `.apkg` for MONO Facts —
  tell the user where it is and how to import it manually. Native image
  occlusion instead requires the user to open Anki and retry.
