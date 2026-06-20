# Anki and Flashcard Best Practices

Use this reference when generating cards, reviewing rubric violations, or
changing scheduler defaults. It separates empirical findings, Anki behavior,
and Mnemo product policy so that defaults are not overstated as universal laws.

## Contents

1. Evidence table
2. Scheduler profile
3. Card design rules
4. Implementation mapping
5. Sources

## Evidence Table

| Topic | Evidence | Practical interpretation | Mnemo rule |
|---|---|---|---|
| Minimum information | Wozniak's formulation guidance recommends simple, minimum-information prompts and learning only understood material. This is influential practitioner guidance, not a controlled estimate of an exact card size. | Test one independently gradable fact at a time. Split enumerations and independent clauses. | Auto-split detectable compound facts; flag ambiguous compounds. Require `Extra` to explain the fact. |
| Working-memory capacity | Cowan (2001) synthesized evidence for a focus-of-attention capacity of roughly four chunks in constrained tasks. This does not directly establish “four items per flashcard.” | Treat four components as a conservative review heuristic, not a biological constant. | Flag answers estimated above four components; require a mnemonic at three or more components. |
| Retrieval practice | Karpicke and Roediger (2008) found repeated retrieval produced large delayed-retention gains, while repeated study after successful recall produced little benefit in their paired-associate task. | A card must require producing an answer before revealing it. Reading a completed statement is review, not retrieval practice. | Use Q&A, cloze, reverse, or image-supported recall prompts; do not generate passive summaries as cards. |
| Spacing | Bahrick et al. (1993) followed four learners for nine years. Thirteen sessions spaced 56 days apart produced retention comparable to 26 sessions spaced 14 days apart. Longer spacing slowed acquisition but improved long-term retention. | Longer intervals can improve durable retention even when practice feels harder. The result used half as many sessions, not a measured claim of exactly half the study time. | Cap new cards/day at 20 as a sustainable workload policy and preserve spaced scheduling. Do not present 20 as an experimentally optimal universal threshold. |
| Interleaving | In Rohrer and Taylor's (2007) second mathematics experiment, interleaved practice yielded 63% versus 20% on a one-week delayed test, despite worse practice performance. Effects depend on material and often benefit discrimination among confusable categories. | Mix topics after initial understanding; do not generalize “3x” to every domain. | Shuffle within topics and schedule topics round-robin to avoid avoidable same-topic runs. |
| Multimedia and dual coding | Mayer's review reported better transfer for relevant explanatory words-plus-pictures than words alone across 11 comparisons. The same review warns that nonexplanatory graphics are unlikely to produce the effect. Clark and Paivio describe linked verbal and nonverbal representations. | Add a relevant diagram or image when it explains or cues the tested relation. Decorative imagery is not evidence-based dual coding. | Use image-supported cards when the source teaches visual or spatial knowledge. Text-only decks may pass; never fabricate decorative media. |
| Front length | No cited study establishes a universal three-second or 20-word flashcard boundary. | Use it as a fast-review usability heuristic. | Require fewer than 20 words on the front and report violations. |
| Format variety | Evidence supports retrieval and appropriate representations, not a universal requirement for three note types per deck. | Variety can reduce repetitive cueing, but duplicate cards can also create workload. | Select formats by semantic fit. Never duplicate or distort a fact merely to meet a format quota. |

## Scheduler Profile

Mnemo's requested default profile is explicitly named `legacy-sm2`:

```json
{
  "learning_steps": ["10m", "1d"],
  "graduating_interval_days": 3,
  "easy_interval_days": 7,
  "starting_ease_percent": 250,
  "max_ease_percent": 250,
  "new_cards_per_day": 20,
  "easy_button_policy": "avoid"
}
```

These values are policy defaults, not a research-proven optimum for every user.
The Anki manual defines learning steps, graduating interval, and Easy interval,
but current Anki guidance recommends that FSRS learning/relearning steps remain
shorter than one day. FSRS does not use legacy ease in the same way and is not
subject to the legacy “ease hell” problem.

Consequences:

- Use `legacy-sm2` for the exact `10m 1d`, 3-day, 7-day, 250% profile.
- Reject a one-day learning step when `scheduler=fsrs`.
- Treat the 250% value as both starting ease and an upper cap in the sidecar.
- Treat “avoid Easy” as study guidance. Portable CSV import cannot remove or
  disable Anki's Easy button; the generator records this limitation rather than
  claiming enforcement it cannot provide.
- Apply the sidecar values manually or through an AnkiConnect preset workflow.
  The generated CSV itself contains notes, not deck-option state.

## Card Design Rules

### Atomicity

1. Split sentence-separated facts.
2. Split semicolon-separated independent clauses.
3. Split detectable `includes/contains/consists of` enumerations into one card
   per component.
4. Flag conjunctions that still appear to join independent propositions.
5. Keep source provenance so a reviewer can repair false splits.

Heuristics cannot prove semantic atomicity. A passing automated report reduces
risk but does not replace review by someone who understands the subject.

### Pre-understanding

Every card must contain:

- `Extra` beginning with `Explanation:`
- `Context:` when prerequisite knowledge may be required
- a specific source location

Do not memorize an unexplained label. If the source does not support an
explanation, report the gap and defer the card.

### Images

Accept images from Markdown (`![alt](url)`) or:

```text
[image: https://example.org/diagram.png | alt: This diagram cues the spatial order of the four chambers.]
```

Alt text must state what the visual cues and why that cue aids recall. A filename
or generic description such as “diagram” is insufficient.

### Mnemonics

For a concept with three or more detected components, generate an acronym from
the component initials and retain the full expansion. Prefer a meaningful visual
association when a human author provides one; deterministic acronym generation
is only a baseline.

## Implementation Mapping

| Rubric item | Generator behavior | Automated audit |
|---|---|---|
| One fact per card | `atomic_units()` splits detectable lists and clauses. | `ATOMICITY_REVIEW`, `COGNITIVE_LOAD` |
| Front under 20 words | Prompt builders prefer short questions/clozes. | `FRONT_TOO_LONG` |
| Appropriate format | Semantic classification chooses direct, cloze, reverse, typed, list, or image-supported treatment. | `CLOZE_FORMAT`, `REVERSE_FORMAT`, `TYPE_FORMAT_MISMATCH` |
| Relevant image | Source image becomes `image-supported`; no image is invented or required. | `IMAGE_ALT` |
| Pre-understanding | `build_extra()` adds explanation and context. | `MISSING_EXPLANATION`, `MISSING_CONTEXT` |
| Mnemonic | Component groups of size 3+ receive an acronym. | `MISSING_MNEMONIC` |
| Interleaving | `interleave_cards()` shuffles within topic and avoids adjacent topics where possible. | `INTERLEAVING` |
| Daily load | Sidecar defaults to 20. | `DAILY_LIMIT` |
| Mature retention | Optional review CSV is filtered to intervals over 21 days and calibration error is logged. | Retention report section |

## Sources

1. Anki Manual, “Deck Options.” Definitions of learning steps, graduating and
   Easy intervals, daily limits, display order, and current FSRS guidance:
   https://docs.ankiweb.net/deck-options.html
2. Wozniak, P. “Effective learning: Twenty rules of formulating knowledge.”
   https://www.supermemo.com/en/blog/twenty-rules-of-formulating-knowledge
3. Cowan, N. (2001). “The magical number 4 in short-term memory: A
   reconsideration of mental storage capacity.” *Behavioral and Brain Sciences,
   24*, 87-114. https://doi.org/10.1017/S0140525X01003922
4. Karpicke, J. D., & Roediger, H. L. (2008). “The critical importance of
   retrieval for learning.” *Science, 319*, 966-968.
   https://doi.org/10.1126/science.1152408
5. Bahrick, H. P., Bahrick, L. E., Bahrick, A. S., & Bahrick, P. E. (1993).
   “Maintenance of foreign language vocabulary and the spacing effect.”
   *Psychological Science, 4*, 316-321.
   https://doi.org/10.1111/j.1467-9280.1993.tb00571.x
6. Rohrer, D., & Taylor, K. (2007). “The shuffling of mathematics problems
   improves learning.” *Instructional Science, 35*, 481-498.
   https://doi.org/10.1007/s11251-007-9015-8
7. Mayer, R. E. (2002). “Multimedia learning.” *Psychology of Learning and
   Motivation, 41*, 85-139. https://doi.org/10.1016/S0079-7421(02)80005-6
8. Clark, J. M., & Paivio, A. (1991). “Dual coding theory and education.”
   *Educational Psychology Review, 3*, 149-210.
   https://doi.org/10.1007/BF01320076
