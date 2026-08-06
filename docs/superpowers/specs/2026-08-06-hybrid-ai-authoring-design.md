# Hybrid AI Authoring Design

## Goal

Reduce brittle hardcoded flashcard-generation heuristics by adding an optional AI authoring stage while keeping Mnemo's deterministic parsing, schema checks, rubric validation, source provenance, and Anki import safety in control.

## Architecture

Mnemo keeps the current offline deterministic path as the default. A new authoring layer exposes a common `CardAuthor` interface with two implementations:

- `DeterministicAuthor`: wraps the existing renderer.
- `JsonAiAuthor`: sends source units to an AI provider and accepts only structured JSON card drafts.

The AI provider is injected. The CLI supports a command provider and a response-file provider so tests and local workflows do not require a specific SDK or network dependency.

## Data Flow

1. CLI reads source text and selects the requested Markdown section.
2. Parser produces `SourceUnit` objects and knowledge metadata.
3. Selected author emits `Card` objects.
4. Existing interleaving, rubric validation, sidecar writing, coverage, ready gate, and import conversion run unchanged.
5. Invalid AI responses fail fast with a user-facing message before CSV output is written.

## Policy Constants

Hardcoded policy values move into `mnemo.pipeline.flashcards.policy`, including Cornell section names, scheduling defaults, list limits, generic prompt stems, classifier cue words, stopwords, abbreviations, technical keywords, and sequence cue words.

## Error Handling

AI mode requires exactly one provider source: `--ai-command` or `--ai-response-file`. Command providers receive the prompt on stdin and must return JSON on stdout. Malformed JSON, missing fields, unknown card types, or empty valid card sets are reported as concise CLI errors.

## Testing

Tests cover deterministic default behavior, policy constant reuse, fake AI response conversion, invalid AI rejection, command-provider prompt flow, and full validator gating on AI-generated cards.
