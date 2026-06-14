# Implementation phases

## Phase 1: core pipeline

Complete: Fact validation, Markdown/PDF/PPTX ingestion, MONO Basic/Cloze/List
types, AnkiConnect import, `.apkg` fallback, and the authoring review gate.

## Phase 2: configuration and interoperability

Complete: optional runtime config, import-time deck/tag defaults, deterministic
target note-type selection, validated field mappings for stock/community note
types, and a standalone MONO note-type installer package.

## Phase 3: richer native cards and offline assets

Complete: bundled offline fonts, `MONO Type` exact-answer cards with native
hints, and live native Image Occlusion imports with rectangle, ellipse, and
polygon masks. Native image occlusion intentionally requires Anki 23.10+ and
AnkiConnect because genanki cannot preserve Anki's stock image-occlusion model
metadata in a portable fallback package.

## Phase 4: domain-neutral semantic planning

Complete: learning objectives, domain-neutral `KnowledgeUnit` classification,
optional semantic Fact metadata, manifest and objective-coverage sidecars,
applicability-based card formats, explicit source grounding, labeled enrichment,
and deferral of ungradable fragments.

## Phase 5: source-format depth and evaluation

Planned: reliable OCR, complex tables, equations, charts, speaker notes, and
source-visual extraction. Calibrate heuristics against approval edits, rejection
reasons, and mature review outcomes from representative real-world decks.
