"""Card authoring strategies for deterministic and AI-assisted generation."""

from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from .models import CARD_TYPES, Card, SourceUnit
from .policy import DEFAULT_AI_COMMAND_TIMEOUT_S
from .render import _build_extra_raw, _field, build_cards, stable_card_id
from .revisions import rendered_card_revision_hash


class AiAuthoringError(ValueError):
    """Raised when an AI authoring provider returns unusable card JSON."""


class CardAuthor(Protocol):
    def author(self, units: Sequence[SourceUnit]) -> list[Card]:
        """Return authored cards for parsed source units."""


class AiProvider(Protocol):
    def complete(self, prompt: str) -> str:
        """Return JSON card drafts for the prompt."""


@dataclass(frozen=True)
class DeterministicAuthor:
    def author(self, units: Sequence[SourceUnit]) -> list[Card]:
        return build_cards(units)


@dataclass(frozen=True)
class FileAiProvider:
    path: Path

    def complete(self, prompt: str) -> str:
        try:
            return self.path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise AiAuthoringError(f"Could not read AI response file: {exc}") from exc


@dataclass(frozen=True)
class CommandAiProvider:
    command: str
    timeout_s: int = DEFAULT_AI_COMMAND_TIMEOUT_S

    def complete(self, prompt: str) -> str:
        try:
            result = subprocess.run(
                shlex.split(self.command),
                input=prompt,
                text=True,
                capture_output=True,
                check=False,
                timeout=self.timeout_s,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AiAuthoringError(f"AI command failed: {exc}") from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or f"exit code {result.returncode}"
            raise AiAuthoringError(f"AI command failed: {detail}")
        return result.stdout


@dataclass(frozen=True)
class JsonAiAuthor:
    provider: AiProvider

    def author(self, units: Sequence[SourceUnit]) -> list[Card]:
        prompt = build_authoring_prompt(units)
        payload = parse_ai_payload(self.provider.complete(prompt))
        drafts = payload.get("cards")
        if not isinstance(drafts, list):
            raise AiAuthoringError("AI response must contain a cards list.")
        units_by_id = {unit.knowledge_unit_id: unit for unit in units}
        cards = [draft_to_card(draft, units_by_id) for draft in drafts]
        if not cards:
            raise AiAuthoringError("AI response did not contain any card drafts.")
        return cards


def build_authoring_prompt(units: Sequence[SourceUnit]) -> str:
    source_units = [
        {
            "source_unit_id": unit.knowledge_unit_id,
            "text": unit.text,
            "question": unit.question,
            "answer": unit.answer,
            "extra": unit.extra,
            "topic": unit.topic,
            "source": unit.source,
            "knowledge_kind": unit.knowledge_kind,
            "learning_purpose": unit.learning_purpose,
        }
        for unit in units
    ]
    return json.dumps(
        {
            "task": "Author source-grounded Anki flashcards. Return JSON only.",
            "schema": {
                "cards": [
                    {
                        "front": "single concrete prompt",
                        "back": "single source-grounded answer",
                        "extra": "why this fact holds",
                        "context": "optional prerequisite background note",
                        "card_type": "qa|cloze|reverse|typed|list",
                        "source_unit_id": "id from source_units",
                        "evidence": "verbatim source span supporting the card",
                        "tags": ["optional-tags"],
                        "confidence": 0.0,
                    }
                ]
            },
            "source_units": source_units,
        },
        ensure_ascii=False,
    )


def parse_ai_payload(text: str) -> dict[str, object]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AiAuthoringError("AI response must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise AiAuthoringError("AI response must be a JSON object.")
    return payload


def draft_to_card(draft: object, units_by_id: dict[str, SourceUnit]) -> Card:
    if not isinstance(draft, dict):
        raise AiAuthoringError("AI card draft must be an object.")
    required = ("front", "back", "extra", "card_type", "source_unit_id", "evidence")
    missing = [field for field in required if not str(draft.get(field, "")).strip()]
    if missing:
        raise AiAuthoringError(f"AI card draft is missing required fields: {', '.join(missing)}")
    source_unit_id = str(draft["source_unit_id"]).strip()
    unit = units_by_id.get(source_unit_id)
    if unit is None:
        raise AiAuthoringError(f"AI card draft references unknown source_unit_id: {source_unit_id}")
    evidence = str(draft["evidence"]).strip()
    if not evidence_is_supported(evidence, unit):
        raise AiAuthoringError("AI card evidence is not present in the referenced source unit.")
    card_type = str(draft["card_type"]).strip()
    if card_type not in CARD_TYPES:
        raise AiAuthoringError(f"AI card draft has unknown card_type: {card_type}")
    raw_front = str(draft["front"])
    raw_back = str(draft["back"])
    raw_tags = draft.get("tags", [])
    tags = [str(tag) for tag in raw_tags if str(tag).strip()] if isinstance(raw_tags, list) else []
    confidence = draft.get("confidence", unit.confidence)
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError) as exc:
        raise AiAuthoringError("AI card confidence must be numeric.") from exc
    raw_extra = str(draft["extra"])
    raw_mnemonic = str(draft.get("mnemonic", ""))
    raw_topic = str(draft.get("topic") or unit.topic)
    raw_source = str(draft.get("source") or unit.source)
    draft_context = str(draft.get("context", "")).strip()
    raw_context = draft_context or _build_extra_raw(unit, raw_front, raw_back)[1]
    front = _field(raw_front)
    back = _field(raw_back)
    context = _field(raw_context)
    escaped_extra = _field(raw_extra)
    escaped_mnemonic = _field(raw_mnemonic)
    escaped_topic = _field(raw_topic)
    escaped_source = _field(raw_source)
    card_tags = [*unit.tags, *tags, "ai-authored", "auto"]
    return Card(
        card_id=stable_card_id(
            raw_front,
            raw_back,
            unit.source,
            unit_id=unit.knowledge_unit_id,
            recall_intent=unit.learning_purpose,
            fact_type=card_type,
        ),
        revision_hash=rendered_card_revision_hash(
            front=raw_front,
            back=raw_back,
            extra=raw_extra,
            context=raw_context,
            mnemonic=raw_mnemonic,
            card_type=card_type,
            tags=card_tags,
            topic=raw_topic,
            source=raw_source,
            image_url="",
            image_alt="",
            knowledge_unit_id=unit.knowledge_unit_id,
            knowledge_kind=unit.knowledge_kind,
            learning_purpose=unit.learning_purpose,
            objective_ids=list(unit.objective_ids),
            prerequisite_ids=list(unit.prerequisite_ids),
            origin=unit.origin,
            confidence=confidence_value,
        ),
        front=front,
        back=back,
        extra=escaped_extra,
        context=context,
        mnemonic=escaped_mnemonic,
        card_type=card_type,
        tags=card_tags,
        topic=escaped_topic,
        source=escaped_source,
        knowledge_unit_id=unit.knowledge_unit_id,
        knowledge_kind=unit.knowledge_kind,
        learning_purpose=unit.learning_purpose,
        objective_ids=list(unit.objective_ids),
        prerequisite_ids=list(unit.prerequisite_ids),
        origin=unit.origin,
        confidence=confidence_value,
    )

def evidence_is_supported(evidence: str, unit: SourceUnit) -> bool:
    haystack = " ".join(
        part for part in (unit.text, unit.question, unit.answer, unit.extra) if part
    )
    return normalize_evidence(evidence) in normalize_evidence(haystack)


def normalize_evidence(value: str) -> str:
    return " ".join(value.casefold().split())
