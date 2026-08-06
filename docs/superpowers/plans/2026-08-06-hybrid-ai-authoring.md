# Hybrid AI Authoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional JSON-based AI authoring stage and centralize flashcard policy constants.

**Architecture:** Keep deterministic generation as the default `CardAuthor`. Add `JsonAiAuthor` with command/file providers and feed its cards through the existing validators and sidecars.

**Tech Stack:** Python 3.11+, argparse, dataclasses, pytest, pytest-cov.

## Global Constraints

- Default behavior remains offline and deterministic.
- AI output must be JSON and must pass Mnemo schema/rubric validation before import.
- No SDK-specific dependency is added.
- Hardcoded policy words move into `mnemo.pipeline.flashcards.policy`.

---

### Task 1: Centralize Policy Constants

**Files:**
- Create: `src/mnemo/pipeline/flashcards/policy.py`
- Modify: `src/mnemo/pipeline/flashcards/models.py`
- Modify: `src/mnemo/pipeline/flashcards/render.py`
- Modify: `src/mnemo/pipeline/flashcards/text.py`
- Modify: `src/mnemo/core/knowledge.py`
- Test: `tests/test_generate_flashcards.py`

**Interfaces:**
- Produces constants such as `CANDIDATE_CARDS_SECTION`, `MAX_LIST_ITEMS`, `DEFAULT_GENERATION_SEED`, and cue-word tuples.

- [ ] Write tests asserting generation uses shared policy constants.
- [ ] Run focused tests and verify they fail before implementation.
- [ ] Add `policy.py` and replace local literal policy values.
- [ ] Run focused tests and full coverage.

### Task 2: Add Authoring Interface

**Files:**
- Create: `src/mnemo/pipeline/flashcards/authoring.py`
- Modify: `src/mnemo/pipeline/generate_flashcards.py`
- Test: `tests/test_ai_authoring.py`

**Interfaces:**
- `CardAuthor.author(units: Sequence[SourceUnit]) -> list[Card]`
- `DeterministicAuthor.author(...)`
- `JsonAiAuthor.author(...)`
- `FileAiProvider.complete(prompt: str) -> str`
- `CommandAiProvider.complete(prompt: str) -> str`

- [ ] Write failing tests for fake AI JSON conversion and malformed JSON rejection.
- [ ] Implement minimal authoring classes.
- [ ] Export authoring APIs through `generate_flashcards.py`.
- [ ] Run focused tests.

### Task 3: Wire CLI Selection

**Files:**
- Modify: `src/mnemo/pipeline/flashcards/cli.py`
- Test: `tests/test_generate_flashcards.py`

**Interfaces:**
- CLI flags: `--author deterministic|ai`, `--ai-response-file`, `--ai-command`.

- [ ] Write failing tests for default deterministic behavior and AI response-file mode.
- [ ] Implement parser options and provider selection.
- [ ] Ensure invalid AI mode exits with code 2 before output.
- [ ] Run focused tests.

### Task 4: Verify

**Files:**
- Existing tests and Science 11 workspace output.

- [ ] Run `uv run pytest --cov=src/mnemo --cov-report=term-missing`.
- [ ] Run Science 11 `mnemo-generate` and `mnemo-ready`.
- [ ] Run `uv tool install --force -e .`.
