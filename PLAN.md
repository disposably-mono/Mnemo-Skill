# Mnemo General Generability Plan

## Product Direction

Mnemo is a domain-neutral, source-grounded Anki authoring system. Its specialty
remains concise, independently gradable retrieval practice. Generality comes from
recognizing knowledge structures rather than accumulating subject profiles.

Division of labor: deterministic scripts ingest, classify, ground, and validate;
the agent authors the cards. The scripts author only what they can ground
specifically and defer the rest — they do not turn unparsed prose into generic
prompts. The deterministic drafter doubles as the offline / no-agent fast path.

## Architecture

1. Ingest source material with page, slide, section, and line provenance.
2. Extract explicit objectives or infer one major-concept objective per topic.
3. Build a `KnowledgeUnit` manifest before generating cards.
4. Classify definitions, relations, comparisons, processes, procedures,
   mechanisms, taxonomies, arguments, narratives, formulas, derivations,
   examples, exceptions, and applications.
5. Select recall treatment by semantic fit while preserving existing Anki note
   types and import paths.
6. Emit cards plus manifest, objective coverage, settings, violations, and
   retention sidecars.
7. Require human approval before import.

## Invariants

- Every assessed claim has source provenance.
- Inferences and generated enrichment are visibly labeled.
- Ambiguous or unsupported units remain visible as deferred or unsupported.
- Atomicity never removes conditions, qualifications, order, units, or necessary
  context.
- Card formats and images are used only when appropriate; no quota manufactures
  artificial variety.
- The deterministic path defers what it cannot ground specifically; it never
  renders a generic "what does the source say" prompt to fill coverage.
- Existing CSV and JSONL inputs remain valid.

## Delivery

- [x] Add the domain-neutral knowledge and objective contracts.
- [x] Add compatible semantic metadata to `Fact` and generated CSV cards.
- [x] Generate manifest and objective-coverage sidecars.
- [x] Select formats from knowledge structure and defer ungradable fragments.
- [x] Replace mandatory variety and imagery with applicability checks.
- [x] Enforce source grounding and enrichment labeling.
- [x] Add benchmarks for factual, comparative, procedural, argumentative,
  narrative, quantitative, exceptional, and mixed material.
- [x] Expand ingestion of scanned text, complex tables, equation candidates,
  structured PPTX chart data, speaker notes, and source visuals with provenance.
- **DEFERRED:** Semantic interpretation of arbitrary PDF charts; PyMuPDF does
  not reliably map vector/image geometry to categories, series, and values.
- [x] Add calibration reporting for approval edits, rejection reasons, and
  mature review outcomes, including Brier scores and prediction buckets.
- **DEFERRED:** Tune generation from representative real-deck outcomes; no
  representative approval and mature-review corpus is available in this repo.

## Acceptance Criteria

- Existing imports and legacy Facts remain compatible.
- Every objective is reported as covered, deferred, unsupported, or omitted.
- Text-only and naturally single-format decks can pass.
- Unsupported assessed claims and unlabeled enrichment fail validation.
- Benchmark decks retain chronology, causal links, ordering, comparison criteria,
  formula conditions, exceptions, and prerequisite links.
- Human approval remains mandatory; target at least 90% first-pass approval after
  collecting a representative evaluation set.
