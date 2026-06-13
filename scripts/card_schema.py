"""The Fact contract: the central, note-type-agnostic data model.

Every component produces or consumes ``Fact`` objects. Ingestion knows nothing
about Anki; the Anki backends know nothing about PDFs; the only smart piece in
between (Claude-driven generation) emits validated Facts. Keeping this contract
small and strict is what lets the rest of the system stay decoupled.

A Fact has a semantic ``type`` (``qa`` / ``cloze`` / ``list`` / ``typed`` /
``image_occlusion``) and a type-specific ``content`` payload. The note-type
adapter (``scripts/adapter``) later renders it into concrete Anki note fields.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FACT_TYPES: tuple[str, ...] = ("qa", "cloze", "list", "typed", "image_occlusion")
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
        if not isinstance(data, dict):
            raise CardValidationError("fact must be a JSON object")
        raw_distractors = data.get("distractors") or []
        if not isinstance(raw_distractors, list):
            raise CardValidationError("distractors must be a list")
        distractors = [_distractor_from_dict(d) for d in raw_distractors]
        content = data.get("content") or {}
        if not isinstance(content, dict):
            raise CardValidationError("content must be an object")
        tags = data.get("tags") or []
        fact = cls(
            type=data.get("type", ""),
            content=dict(content),
            deck=data.get("deck", ""),
            tags=tags,
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

    if fact.source is not None and not isinstance(fact.source, str):
        raise CardValidationError("source must be a string when provided")

    if fact.distractors and fact.type not in {"qa", "cloze"}:
        raise CardValidationError(
            f"distractors are not allowed on {fact.type!r} facts"
        )

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
    _validate_optional_str(content, "extra", "cloze")


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
    _validate_optional_str(content, "extra", "list")


def _validate_typed(content: dict[str, Any]) -> None:
    _require_nonempty_str(content, "prompt", "typed")
    _require_nonempty_str(content, "answer", "typed")
    hints = content.get("hints", [])
    if not isinstance(hints, list):
        raise CardValidationError("typed content 'hints' must be a list of strings")
    if len(hints) > 3:
        raise CardValidationError("typed content supports at most three hints")
    for hint in hints:
        if not isinstance(hint, str) or not hint.strip():
            raise CardValidationError("each typed hint must be a non-empty string")
    _validate_optional_str(content, "extra", "typed")


def _validate_image_occlusion(content: dict[str, Any]) -> None:
    _require_nonempty_str(content, "image", "image_occlusion")
    masks = content.get("masks")
    if not isinstance(masks, list) or not masks:
        raise CardValidationError(
            "image_occlusion content requires at least one mask"
        )
    for mask in masks:
        _validate_occlusion_mask(mask)
    for key in ("header", "back_extra", "comments"):
        _validate_optional_str(content, key, "image_occlusion")
    occlude_inactive = content.get("occlude_inactive", True)
    if not isinstance(occlude_inactive, bool):
        raise CardValidationError(
            "image_occlusion content 'occlude_inactive' must be true or false"
        )


def _validate_optional_str(content: dict[str, Any], key: str, kind: str) -> None:
    if key in content and not isinstance(content[key], str):
        raise CardValidationError(f"{kind} content {key!r} must be a string")


def _validate_occlusion_mask(mask: Any) -> None:
    if not isinstance(mask, dict):
        raise CardValidationError("each image occlusion mask must be an object")
    shape = mask.get("shape")
    if shape not in {"rect", "ellipse", "polygon"}:
        raise CardValidationError(
            "image occlusion mask shape must be 'rect', 'ellipse', or 'polygon'"
        )
    card = mask.get("card")
    if card is not None and (
        isinstance(card, bool) or not isinstance(card, int) or card < 1
    ):
        raise CardValidationError("image occlusion mask 'card' must be a positive integer")

    if shape == "polygon":
        for key in ("left", "top"):
            _validate_normalized_number(mask.get(key), f"mask {key}")
        points = mask.get("points")
        if not isinstance(points, list) or len(points) < 3:
            raise CardValidationError("polygon masks require at least three points")
        for point in points:
            if not isinstance(point, list) or len(point) != 2:
                raise CardValidationError("polygon points must be [x, y] pairs")
            _validate_normalized_number(point[0], "polygon x")
            _validate_normalized_number(point[1], "polygon y")
        return

    for key in ("left", "top"):
        _validate_normalized_number(mask.get(key), f"mask {key}")
    size_keys = ("width", "height") if shape == "rect" else ("rx", "ry")
    for key in size_keys:
        value = mask.get(key)
        _validate_normalized_number(value, f"mask {key}")
        if value == 0:
            raise CardValidationError(f"mask {key} must be greater than zero")


def _validate_normalized_number(value: Any, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CardValidationError(f"{label} must be a number between 0 and 1")
    if value < 0 or value > 1:
        raise CardValidationError(f"{label} must be between 0 and 1")


_CONTENT_VALIDATORS = {
    "qa": _validate_qa,
    "cloze": _validate_cloze,
    "list": _validate_list,
    "typed": _validate_typed,
    "image_occlusion": _validate_image_occlusion,
}


# --- JSONL persistence ------------------------------------------------------

def dump_facts(facts: list[Fact], path: str | Path) -> None:
    """Write Facts as one JSON object per line (JSONL)."""
    path = Path(path)
    with path.open("w", encoding="utf-8") as fh:
        for fact in facts:
            fh.write(json.dumps(fact.to_dict(), ensure_ascii=False))
            fh.write("\n")


def load_facts(
    path: str | Path,
    *,
    default_deck: str | None = None,
    auto_tag: str | None = None,
) -> list[Fact]:
    """Read and validate Facts, applying optional import-time defaults."""
    path = Path(path)
    facts: list[Fact] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            if default_deck and not str(data.get("deck", "")).strip():
                data["deck"] = default_deck
            if auto_tag:
                tags = list(data.get("tags") or [])
                if auto_tag not in tags:
                    tags.append(auto_tag)
                data["tags"] = tags
            facts.append(Fact.from_dict(data))
    return facts
