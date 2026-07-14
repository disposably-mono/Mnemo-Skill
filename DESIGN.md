# Verbatim Block Handling

## Semantic and rendering model

Code and math do not add a `FACT_TYPE`. They are source representations, not a
new learning interaction: a grounded QA or cloze Fact can test either one.
Keeping the existing semantic registry avoids duplicating validation, mappings,
and import behavior. `MONO Code` is therefore a rendering target for QA Facts
whose source unit is code, selected by card-type policy rather than a new Fact
type. Display math and multiline code are not typed cards because exact-string
entry is inappropriate for notation and code.

## Inline masking

Inline backtick code, `\\( ... \\)`, and single-dollar math spans are replaced
temporarily with collision-resistant sentinels (`\x1eVERBATIM:<index>\x1f`) and
restored after an operation. The masked text is used by `_FACT_BOUNDARY`,
`split_list_items`, `split_independent_clauses`, `word_count`,
`estimate_components`, `looks_compound`, and cloze detection. This keeps
punctuation, conjunctions, notation words, and literal cloze-like text inside
verbatim spans opaque to prose heuristics while preserving their original
surface form for rendering.
