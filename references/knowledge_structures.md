# Knowledge Structure Authoring

Use this reference after ingestion and before card authoring. Classify what the
source teaches independently of its academic subject. The classification guides
retrieval treatment; it does not require a unique Anki note type.

## Grounding

- `source`: directly taught by the cited source.
- `inferred`: a defensible synthesis requiring an explicit `Inference:` label.
- `generated-enrichment`: a new example or practice item requiring a visible
  `Enrichment:` label and provenance describing what source it was generated from.
- Defer material that cannot be made independently gradable without inventing a
  missing premise, interpretation, value, or answer.

## Structures

| Structure | Preserve | Preferred retrieval |
|---|---|---|
| Definition | term, scope, qualifications | forward Q&A; reverse only when unique |
| Relation | subject, relation, object | short Q&A or constrained cloze |
| Comparison | criterion and both sides | one criterion per card plus an overview when useful |
| Ordered process | order and transition | step recall or ordered list; never flatten order |
| Procedure | prerequisites, decisions, exceptions, recovery | scenario-specific Q&A and branch cards |
| Mechanism | cause, intermediate link, result | why/how Q&A; split only at independently useful links |
| Taxonomy | parent, member, membership criterion | member cards plus a small list overview |
| Argument | claim, evidence, assumption, objection, conclusion | one role or relation per card |
| Narrative | event, actor, motivation, chronology, causal link, turning point | event and causal Q&A, not chapter summaries |
| Formula | notation, domain, units, assumptions | typed formula and variable/condition cards |
| Derivation | starting conditions and justified transitions | one justified step per card plus reconstruction practice |
| Example | concept illustrated and why it qualifies | identify the concept or explain the fit |
| Exception | general rule, boundary, exception | contrastive Q&A with the triggering condition |
| Application | givens, target, method, answer criteria | labeled enrichment unless directly supplied by the source |

## Format Selection

- Use Q&A for causes, consequences, explanations, distinctions, and explicit facts.
- Use cloze only when the remaining context identifies one intended answer.
- Use typed recall when exact characters or notation matter.
- Use lists only when the set itself is meaningful; preserve ordered versus
  unordered semantics in the title and explanation.
- Use image occlusion only for visual location or identification.
- Keep answer-side confusions plausible and source-relevant; never turn them into
  recognition questions.

## Coverage Review

Review major objectives, not raw card count. Every objective must be one of:

- `covered`: at least one represented unit tests the objective.
- `deferred`: the source contains relevant material but it is not safely cardable.
- `unsupported`: the objective is stated but the source lacks teachable support.
- `omitted`: intentionally excluded as low-value or out of requested scope.

Do not hide deferred or unsupported units by deleting them from the manifest.
