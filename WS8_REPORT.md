# WS8 identity and revision report

Implemented stable semantic identities for generated cards, deterministic
revision hashes covering note-visible content (including distractors), and
recomputation of stale canonical hashes at adaptation boundaries. Duplicate
same-unit variants receive deterministic occurrence slots rather than changing
IDs during ordinary editorial edits.

Verification: isolated full suite passed; focused identity/generation tests
cover duplicate variants, stable IDs, distractor changes, and stale hashes.

Residual risk: legacy inputs without explicit per-target IDs still use a
deterministic variant slot when duplicate semantic identities occur.
