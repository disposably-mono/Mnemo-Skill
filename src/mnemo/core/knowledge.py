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

from .knowledge_policy import KNOWLEDGE_KIND_CUES


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
# Per-KnowledgeUnit coverage states. NOTE: objective-level status in
# build_coverage_report uses a parallel but distinct vocabulary
# ("covered"/"deferred"/"unsupported"/"omitted") where "covered" replaces a
# unit's "represented" — keep the two sets in sync if either changes.
COVERAGE_STATUSES = ("represented", "deferred", "unsupported", "omitted")

_OBJECTIVE = re.compile(
    r"^(?:learning\s+)?objectives?\s*:\s*(?P<label>.+)$", re.IGNORECASE
)
_OBJECTIVE_HEADER = re.compile(r"^(?:learning\s+)?objectives?\s*:\s*$", re.IGNORECASE)
_BULLET = re.compile(r"^\s*(?:[-*+] |\d+[.)]\s+)(?P<label>.+)$")
# Strong objective framing, recognized anywhere in the source: Bloom's-style
# "should/will be able to", or an explicit "by the end of this lesson ..."
# outcome (which stays an objective even when phrased with a bare "can").
_OUTCOME_STRONG = re.compile(
    r"^(?:by the end of (?:this )?(?:lesson|lecture|chapter),?\s*"
    r"(?:students?|learners?|you) (?:should be able to|will be able to|can)"
    r"|(?:students?|learners?|you) (?:should be able to|will be able to))"
    r"\s+(?P<label>.+)$",
    re.IGNORECASE,
)
# Weak framing: a bare "you can <verb>" is an objective only inside an explicit
# objectives block. In body prose it is ordinary content ("You can compute
# variance as ...") that must become a card, not be silently dropped.
_OUTCOME_CAN = re.compile(
    r"^(?:students?|learners?|you) can\s+(?P<label>.+)$",
    re.IGNORECASE,
)


def objective_label(line: str, raw: str, *, in_block: bool) -> str | None:
    """Return the learning-objective label a line states, or None if it is content.

    Strong framing (``Objectives:``, ``should/will be able to``, an explicit
    ``by the end of this lesson ...`` outcome) is recognized anywhere. A bare
    ``you can ...`` counts as an objective only when ``in_block`` (under an
    ``Objectives:`` header), so declarative ``You can compute ...`` prose is
    left to become a card. ``line`` is the stripped text; ``raw`` preserves
    leading whitespace so bullet markers still match inside a block.
    """
    match = _OBJECTIVE.match(line) or _OUTCOME_STRONG.match(line)
    if match:
        return match.group("label").strip(" .")
    if in_block:
        bullet = _BULLET.match(raw)
        if bullet:
            return bullet.group("label").strip(" .")
        weak = _OUTCOME_CAN.match(line)
        if weak:
            return weak.group("label").strip(" .")
    return None


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

    if has_cue(lower, "example"):
        return "example", "interpret"
    if has_cue(lower, "exception"):
        return "exception", "discriminate"
    if has_cue(lower, "application"):
        return "application", "apply"
    if has_cue(lower, "derivation"):
        return "derivation", "derive"
    if _looks_like_formula(value):
        return "formula", "apply"
    if has_cue(lower, "argument"):
        return "argument", "interpret"
    if has_cue(lower, "procedure"):
        return "procedure", "sequence"
    if has_cue(lower, "ordered-process"):
        return "ordered-process", "sequence"
    if has_cue(lower, "narrative"):
        return "narrative", "sequence"
    if has_cue(lower, "comparison"):
        return "comparison", "discriminate"
    if has_cue(lower, "mechanism"):
        return "mechanism", "explain"
    if has_cue(lower, "taxonomy"):
        return "taxonomy", "recall"
    if has_cue(lower, "definition") or re.match(
        r"^[^.!?]{1,80}\s+is\s+[^.!?]+[.!?]?$", value, re.IGNORECASE
    ):
        return "definition", "recall"
    if has_cue(lower, "relation"):
        return "relation", "recall"
    return "fact", "recall"


def has_cue(text: str, group: str) -> bool:
    return any(
        re.search(rf"\b{re.escape(cue)}\b", text)
        for cue in KNOWLEDGE_KIND_CUES[group]
    )


def _looks_like_formula(text: str) -> bool:
    if has_cue(text.casefold(), "formula"):
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
        label = objective_label(line, raw, in_block=objective_block)
        if label is None:
            objective_block = False
            continue
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
    # IDs key on (topic, source_name); distinct sources keep distinct ids, and
    # duplicate topics within one source are collapsed by dict.fromkeys below.
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
