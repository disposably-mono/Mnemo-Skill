"""Domain-neutral knowledge planning and objective coverage.

This module describes what a source teaches before Mnemo decides how to test it.
The contract stays independent of Anki so semantic coverage can be reviewed even
when a unit is deferred or intentionally omitted from a deck.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


KNOWLEDGE_KINDS = (
    "fact",
    "definition",
    "relation",
    "comparison",
    "ordered-process",
    "procedure",
    "mechanism",
    "taxonomy",
    "argument",
    "narrative",
    "formula",
    "derivation",
    "example",
    "exception",
    "application",
)
LEARNING_PURPOSES = (
    "recall",
    "discriminate",
    "sequence",
    "explain",
    "interpret",
    "derive",
    "apply",
)
ORIGINS = ("source", "inferred", "generated-enrichment")
COVERAGE_STATUSES = ("represented", "deferred", "unsupported", "omitted")

_OBJECTIVE = re.compile(
    r"^(?:learning\s+)?objectives?\s*:\s*(?P<label>.+)$", re.IGNORECASE
)
_OBJECTIVE_HEADER = re.compile(r"^(?:learning\s+)?objectives?\s*:\s*$", re.IGNORECASE)
_BULLET = re.compile(r"^\s*(?:[-*+] |\d+[.)]\s+)(?P<label>.+)$")
_OUTCOME = re.compile(
    r"^(?:by the end of (?:this )?(?:lesson|lecture|chapter),?\s*)?"
    r"(?:students?|learners?|you) (?:should be able to|will be able to|can)\s+"
    r"(?P<label>.+)$",
    re.IGNORECASE,
)


class KnowledgeValidationError(ValueError):
    """Raised when semantic planning metadata is invalid."""


@dataclass(frozen=True)
class LearningObjective:
    id: str
    label: str
    topic: str
    source: str
    explicit: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class KnowledgeUnit:
    id: str
    text: str
    kind: str
    purpose: str
    topic: str
    source: str
    objective_ids: list[str] = field(default_factory=list)
    prerequisite_ids: list[str] = field(default_factory=list)
    origin: str = "source"
    confidence: float = 1.0
    status: str = "represented"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_knowledge_unit(self)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def stable_id(prefix: str, *values: str) -> str:
    payload = "\0".join(values).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(payload).hexdigest()[:12]}"


def validate_knowledge_unit(unit: KnowledgeUnit) -> None:
    if not unit.id.strip() or not unit.text.strip() or not unit.source.strip():
        raise KnowledgeValidationError("knowledge units require id, text, and source")
    if unit.kind not in KNOWLEDGE_KINDS:
        raise KnowledgeValidationError(f"unknown knowledge kind: {unit.kind!r}")
    if unit.purpose not in LEARNING_PURPOSES:
        raise KnowledgeValidationError(f"unknown learning purpose: {unit.purpose!r}")
    if unit.origin not in ORIGINS:
        raise KnowledgeValidationError(f"unknown origin: {unit.origin!r}")
    if unit.status not in COVERAGE_STATUSES:
        raise KnowledgeValidationError(f"unknown coverage status: {unit.status!r}")
    if isinstance(unit.confidence, bool) or not 0 <= unit.confidence <= 1:
        raise KnowledgeValidationError("confidence must be between 0 and 1")


def classify_knowledge(text: str, question: str = "") -> tuple[str, str]:
    """Classify source material by structure, using conservative heuristics."""
    value = f"{question} {text}".strip()
    lower = value.casefold()

    if re.search(r"\b(?:example|for example|for instance|such as)\b", lower):
        return "example", "interpret"
    if re.search(r"\b(?:except|exception|unless|however|but not|only when)\b", lower):
        return "exception", "discriminate"
    if re.search(r"\b(?:calculate|compute|solve|apply|given that|scenario)\b", lower):
        return "application", "apply"
    if re.search(r"\b(?:derive|derivation|prove|proof)\b", lower):
        return "derivation", "derive"
    if _looks_like_formula(value):
        return "formula", "apply"
    if re.search(r"\b(?:claim|evidence|premise|conclusion|argues?|therefore|objection)\b", lower):
        return "argument", "interpret"
    if re.search(r"\b(?:steps?|procedure|instructions?|how to)\b", lower):
        return "procedure", "sequence"
    if re.search(r"\b(?:first|second|third|finally|stage|phase)\b", lower):
        return "ordered-process", "sequence"
    if re.search(r"\b(?:before|after|then|eventually|turning point|protagonist)\b", lower):
        return "narrative", "sequence"
    if re.search(r"\b(?:versus|compared with|differs? from|whereas|unlike|similar)\b", lower):
        return "comparison", "discriminate"
    if re.search(r"\b(?:because|causes?|results? in|leads? to|thereby|through which)\b", lower):
        return "mechanism", "explain"
    if re.search(r"\b(?:includes?|contains?|consists of|types? of|categories of)\b", lower):
        return "taxonomy", "recall"
    if re.search(r"\b(?:is defined as|means|refers to|what is|define)\b", lower) or re.match(
        r"^[^.!?]{1,80}\s+is\s+[^.!?]+[.!?]?$", value, re.IGNORECASE
    ):
        return "definition", "recall"
    if re.search(r"\b(?:is|are|has|have|uses?|produces?|requires?|prevents?|allows?)\b", lower):
        return "relation", "recall"
    return "fact", "recall"


def _looks_like_formula(text: str) -> bool:
    if re.search(r"\b(?:formula|equation|equals?|ratio|rate|percentage)\b", text, re.I):
        return True
    return bool(
        re.search(r"(?:[A-Za-z][A-Za-z0-9_]*|\d+)\s*=\s*[^=]", text)
        or re.search(r"\\(?:frac|sum|int|sqrt)\b", text)
    )


def extract_explicit_objectives(text: str, source_name: str) -> list[LearningObjective]:
    objectives: list[LearningObjective] = []
    topic = "General"
    objective_block = False
    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            objective_block = False
            continue
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if heading:
            topic = heading.group(1).strip()
            objective_block = False
            continue
        if _OBJECTIVE_HEADER.match(line):
            objective_block = True
            continue
        match = _OBJECTIVE.match(line) or _OUTCOME.match(line)
        if not match and objective_block:
            match = _BULLET.match(raw)
        if not match:
            objective_block = False
            continue
        label = match.group("label").strip(" .")
        source = f"{source_name}:line-{line_number}"
        objectives.append(
            LearningObjective(
                id=stable_id("objective", label, source),
                label=label,
                topic=topic,
                source=source,
                explicit=True,
            )
        )
    return objectives


def infer_topic_objectives(
    topics: Iterable[str], source_name: str
) -> list[LearningObjective]:
    return [
        LearningObjective(
            id=stable_id("objective", topic, source_name),
            label=f"Understand and recall the major concepts in {topic}",
            topic=topic,
            source=source_name,
            explicit=False,
        )
        for topic in dict.fromkeys(topic.strip() or "General" for topic in topics)
    ]


def build_coverage_report(
    objectives: Iterable[LearningObjective], units: Iterable[KnowledgeUnit]
) -> dict[str, Any]:
    objective_list = list(objectives)
    unit_list = list(units)
    by_objective: list[dict[str, Any]] = []
    for objective in objective_list:
        members = [unit for unit in unit_list if objective.id in unit.objective_ids]
        statuses = {unit.status for unit in members}
        status = "covered" if "represented" in statuses else (
            next(iter(statuses)) if len(statuses) == 1 else "unsupported"
        )
        if not members:
            status = "unsupported"
        by_objective.append(
            {
                **objective.to_dict(),
                "status": status,
                "knowledge_units": len(members),
                "represented_units": sum(unit.status == "represented" for unit in members),
            }
        )

    status_counts = {
        status: sum(unit.status == status for unit in unit_list)
        for status in COVERAGE_STATUSES
    }
    covered = sum(item["status"] == "covered" for item in by_objective)
    return {
        "objectives": by_objective,
        "summary": {
            "objectives": len(by_objective),
            "covered_objectives": covered,
            "objective_coverage": round(covered / len(by_objective), 4)
            if by_objective
            else 0.0,
            "knowledge_units": len(unit_list),
            **status_counts,
        },
    }
