"""The Fact contract: the central, note-type-agnostic data model.

Every component produces or consumes ``Fact`` objects. Ingestion knows nothing
about Anki; the Anki backends know nothing about PDFs; the only smart piece in
between (Claude-driven generation) emits validated Facts. Keeping this contract
small and strict is what lets the rest of the system stay decoupled.

A Fact has a semantic ``type`` (``qa`` / ``cloze`` / ``list``) and a
type-specific ``content`` payload. The note-type adapter (``scripts/adapter``)
later renders a Fact into concrete Anki note fields.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FACT_TYPES: tuple[str, ...] = ("qa", "cloze", "list")
GRADES: tuple[str, ...] = ("far", "medium", "near")

# A cloze deletion looks like {{c1::answer}} (optionally {{c1::answer::hint}}).
_CLOZE_MARKER = re.compile(r"\{\{c\d+::")

# Anki splits tags on whitespace, so a tag may not contain any.
_WHITESPACE = re.compile(r"\s")

_MIN_LIST_ITEMS = 2


class CardValidationError(ValueError):
    """Raised when a Fact (or one of its parts) violates the contract."""


@dataclass
class Distractor:
    """A plausible-but-wrong answer, shown answer-side as a 'confusion'.

    ``grade`` ranks how close the distractor is to correct: ``near`` (easily
    confused), ``medium``, or ``far`` (obviously wrong).
    """

    text: str
    grade: str

    def to_dict(self) -> dict[str, str]:
        return {"text": self.text, "grade": self.grade}


@dataclass
class Fact:
    """A note-type-agnostic unit of knowledge to be turned into card(s)."""

    type: str
    content: dict[str, Any]
    deck: str
    tags: list[str] = field(default_factory=list)
    source: str | None = None
    distractors: list[Distractor] = field(default_factory=list)

    # --- construction -------------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Fact":
        """Build and validate a Fact from a plain dict (e.g. JSON line)."""
        raw_distractors = data.get("distractors") or []
        distractors = [_distractor_from_dict(d) for d in raw_distractors]
        fact = cls(
            type=data.get("type", ""),
            content=dict(data.get("content") or {}),
            deck=data.get("deck", ""),
            tags=list(data.get("tags") or []),
            source=data.get("source"),
            distractors=distractors,
        )
        validate_fact(fact)
        return fact

    # --- serialization ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "type": self.type,
            "content": self.content,
            "deck": self.deck,
            "tags": self.tags,
        }
        # Only emit optional keys when they carry information, but always emit
        # them together so round-tripping a fully-specified Fact is exact.
        if self.source is not None:
            out["source"] = self.source
        if self.distractors:
            out["distractors"] = [d.to_dict() for d in self.distractors]
        return out


def _distractor_from_dict(data: Any) -> Distractor:
    if not isinstance(data, dict):
        raise CardValidationError(f"distractor must be an object, got {type(data).__name__}")
    text = data.get("text", "")
    grade = data.get("grade", "")
    if not isinstance(text, str) or not text.strip():
        raise CardValidationError("distractor requires non-empty 'text'")
    if grade not in GRADES:
        raise CardValidationError(
            f"distractor 'grade' must be one of {GRADES}, got {grade!r}"
        )
    return Distractor(text=text, grade=grade)


# --- validation -------------------------------------------------------------

def validate_fact(fact: Fact) -> None:
    """Validate a Fact in place; raise CardValidationError on any violation."""
    if fact.type not in FACT_TYPES:
        raise CardValidationError(
            f"unknown fact type {fact.type!r}; must be one of {FACT_TYPES}"
        )

    if not isinstance(fact.deck, str) or not fact.deck.strip():
        raise CardValidationError("deck must be a non-empty string")

    _validate_tags(fact.tags)

    if fact.distractors and fact.type == "list":
        raise CardValidationError("distractors are not allowed on 'list' facts")

    _CONTENT_VALIDATORS[fact.type](fact.content)


def _validate_tags(tags: list[str]) -> None:
    if not isinstance(tags, list):
        raise CardValidationError("tags must be a list of strings")
    for tag in tags:
        if not isinstance(tag, str) or not tag.strip():
            raise CardValidationError("each tag must be a non-empty string")
        if _WHITESPACE.search(tag):
            raise CardValidationError(f"tag {tag!r} may not contain whitespace")


def _require_nonempty_str(content: dict[str, Any], key: str, kind: str) -> None:
    value = content.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CardValidationError(f"{kind} content requires non-empty {key!r}")


def _validate_qa(content: dict[str, Any]) -> None:
    _require_nonempty_str(content, "front", "qa")
    _require_nonempty_str(content, "back", "qa")


def _validate_cloze(content: dict[str, Any]) -> None:
    text = content.get("text")
    if not isinstance(text, str) or not text.strip():
        raise CardValidationError("cloze content requires non-empty 'text'")
    if not _CLOZE_MARKER.search(text):
        raise CardValidationError(
            "cloze content must contain a cloze deletion like {{c1::answer}}"
        )


def _validate_list(content: dict[str, Any]) -> None:
    _require_nonempty_str(content, "title", "list")
    items = content.get("items")
    if not isinstance(items, list) or len(items) < _MIN_LIST_ITEMS:
        raise CardValidationError(
            f"list content requires 'items' with at least {_MIN_LIST_ITEMS} entries"
        )
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise CardValidationError("each list item must be a non-empty string")


_CONTENT_VALIDATORS = {
    "qa": _validate_qa,
    "cloze": _validate_cloze,
    "list": _validate_list,
}


# --- JSONL persistence ------------------------------------------------------

def dump_facts(facts: list[Fact], path: str | Path) -> None:
    """Write Facts as one JSON object per line (JSONL)."""
    path = Path(path)
    with path.open("w", encoding="utf-8") as fh:
        for fact in facts:
            fh.write(json.dumps(fact.to_dict(), ensure_ascii=False))
            fh.write("\n")


def load_facts(path: str | Path) -> list[Fact]:
    """Read and validate Facts from a JSONL file."""
    path = Path(path)
    facts: list[Fact] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            facts.append(Fact.from_dict(json.loads(line)))
    return facts
