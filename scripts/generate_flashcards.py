#!/usr/bin/env python3
"""Generate rubric-audited, Anki-compatible flashcards from study notes.

The generator is deliberately deterministic and conservative. It can recognize
common note structures and split obvious compound facts, but it reports
ambiguous cases for human review instead of pretending heuristic NLP is exact.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import random
import re
import sys
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.knowledge import (
    KNOWLEDGE_KINDS,
    LEARNING_PURPOSES,
    ORIGINS,
    KnowledgeUnit,
    LearningObjective,
    build_coverage_report,
    classify_knowledge,
    extract_explicit_objectives,
    infer_topic_objectives,
    stable_id,
)


CSV_FIELDS = (
    "Front",
    "Back",
    "Extra",
    "Mnemonic",
    "CardType",
    "Tags",
    "ImageURL",
    "ImageAlt",
    "Topic",
    "Source",
    "CardID",
    "KnowledgeUnitID",
    "KnowledgeKind",
    "LearningPurpose",
    "ObjectiveIDs",
    "PrerequisiteIDs",
    "Origin",
    "Confidence",
)
CARD_TYPES = ("qa", "cloze", "reverse", "typed", "list", "image-supported")
MAX_FRONT_WORDS = 19  # Rubric says fewer than 20 words.
MAX_COMPONENTS = 4
DEFAULT_SEED = 42

_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
_IMAGE_MD = re.compile(r"!\[([^]]*)\]\(([^)\s]+)(?:\s+['\"][^'\"]*['\"])?\)")
_IMAGE_DIRECTIVE = re.compile(
    r"^\[image:\s*(?P<url>[^|\]]+)\|\s*alt:\s*(?P<alt>[^\]]+)\]$",
    re.IGNORECASE,
)
_QA_LINE = re.compile(r"^(?:Q(?:uestion)?):\s*(.+)$", re.IGNORECASE)
_ANSWER_LINE = re.compile(r"^(?:A(?:nswer)?):\s*(.+)$", re.IGNORECASE)
_EXTRA_LINE = re.compile(r"^Extra:\s*(.+)$", re.IGNORECASE)
_TOPIC_LINE = re.compile(r"^Topic:\s*(.+)$", re.IGNORECASE)
_TAGS_LINE = re.compile(r"^Tags?:\s*(.+)$", re.IGNORECASE)
_OBJECTIVE_LINE = re.compile(
    r"^(?:(?:learning\s+)?objectives?\s*:|"
    r"(?:students?|learners?|you) (?:should be able to|will be able to|can)\s+)",
    re.IGNORECASE,
)
_OBJECTIVE_HEADER = re.compile(r"^(?:learning\s+)?objectives?\s*:\s*$", re.IGNORECASE)
_BULLET = re.compile(r"^\s*(?:[-*+] |\d+[.)]\s+)(.+)$")
_CLOZE = re.compile(r"\{\{c\d+::(.*?)(?:::[^}]*)?\}\}")
_WORDS = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")
_FACT_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_MULTI_SIGNAL = re.compile(
    r"(?:;|\b(?:first|second|third|finally)\b|\b(?:and|but|whereas|while)\b)",
    re.IGNORECASE,
)
# Shared relational-verb vocabulary. A narrow list silently drops ordinary
# declarative facts (e.g. "converts", "forms", "encodes") because render_prompt
# can find no relation to test. Keep this single source of truth so _VERB and
# _RELATION never diverge.
_REL_VERB_ALT = (
    r"is|are|was|were|has|have|includes?|contains?|consists?|comprises?|causes?|"
    r"means?|refers?|requires?|uses?|produces?|prevents?|allows?|converts?|forms?|"
    r"binds?|regulates?|encodes?|represents?|transmits?|occurs?|releases?|"
    r"generates?|stores?|transfers?|transports?|controls?|determines?|describes?|"
    r"defines?|equals?|measures?|involves?|enables?|reduces?|increases?|decreases?"
)
_VERB = re.compile(rf"\b(?:{_REL_VERB_ALT})\b", re.IGNORECASE)
_DEFINITION = re.compile(
    r"^(?P<subject>.+?)\s+(?:is|means|refers to)\s+(?P<object>.+?)[.!?]?$",
    re.IGNORECASE,
)
_WHAT_IS = re.compile(r"^What is\s+(?P<term>.+?)\??$", re.IGNORECASE)
_DEFINE = re.compile(r"^Define\s+(?P<term>.+?)\.?$", re.IGNORECASE)
_WHAT_MEANS = re.compile(r"^What does\s+(?P<term>.+?)\s+mean\??$", re.IGNORECASE)
_RELATION = re.compile(
    rf"^(?P<subject>.+?)\s+(?P<verb>{_REL_VERB_ALT})\s+(?P<object>.+?)[.!?]?$",
    re.IGNORECASE,
)
_LIST_STATEMENT = re.compile(
    r"^(?P<subject>.+?)\s+(?P<verb>includes?|contains?|consists of|has|has three|"
    r"has four)\s+(?P<items>.+?)[.!?]?$",
    re.IGNORECASE,
)
_TECHNICAL = re.compile(
    r"\b[A-Z]{2,}\b|\b(?:theorem|algorithm|enzyme|protocol|doctrine|statute|"
    r"coefficient|derivative|mitosis|syntax|jurisdiction)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class GenerationConfig:
    learning_steps: tuple[str, ...] = ("10m", "1d")
    graduating_interval_days: int = 3
    easy_interval_days: int = 7
    starting_ease_percent: int = 250
    max_ease_percent: int = 250
    new_cards_per_day: int = 20
    scheduler: str = "legacy-sm2"
    easy_button_policy: str = "avoid"
    interleave_topics: bool = True
    seed: int = DEFAULT_SEED


@dataclass
class SourceUnit:
    text: str
    topic: str
    source: str
    question: str = ""
    answer: str = ""
    extra: str = ""
    tags: list[str] = field(default_factory=list)
    image_url: str = ""
    image_alt: str = ""
    group_components: list[str] = field(default_factory=list)
    knowledge_unit_id: str = ""
    knowledge_kind: str = "fact"
    learning_purpose: str = "recall"
    objective_ids: list[str] = field(default_factory=list)
    prerequisite_ids: list[str] = field(default_factory=list)
    origin: str = "source"
    confidence: float = 1.0


@dataclass
class Card:
    front: str
    back: str
    extra: str
    mnemonic: str
    card_type: str
    tags: list[str]
    topic: str
    source: str
    image_url: str = ""
    image_alt: str = ""
    card_id: str = ""
    knowledge_unit_id: str = ""
    knowledge_kind: str = "fact"
    learning_purpose: str = "recall"
    objective_ids: list[str] = field(default_factory=list)
    prerequisite_ids: list[str] = field(default_factory=list)
    origin: str = "source"
    confidence: float = 1.0

    def to_row(self) -> dict[str, str]:
        return {
            "Front": self.front,
            "Back": self.back,
            "Extra": self.extra,
            "Mnemonic": self.mnemonic,
            "CardType": self.card_type,
            "Tags": " ".join(dict.fromkeys(self.tags)),
            "ImageURL": self.image_url,
            "ImageAlt": self.image_alt,
            "Topic": self.topic,
            "Source": self.source,
            "CardID": self.card_id,
            "KnowledgeUnitID": self.knowledge_unit_id,
            "KnowledgeKind": self.knowledge_kind,
            "LearningPurpose": self.learning_purpose,
            "ObjectiveIDs": " ".join(self.objective_ids),
            "PrerequisiteIDs": " ".join(self.prerequisite_ids),
            "Origin": self.origin,
            "Confidence": f"{self.confidence:.4f}",
        }


@dataclass(frozen=True)
class Violation:
    level: str
    code: str
    message: str
    card_id: str = ""
    action: str = ""


def word_count(text: str) -> int:
    return len(_WORDS.findall(strip_html_and_cloze(text)))


def strip_html_and_cloze(text: str) -> str:
    text = _CLOZE.sub(lambda match: match.group(1), text)
    return re.sub(r"<[^>]+>", " ", text)


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "general"


def parse_content(text: str, source_name: str = "input") -> list[SourceUnit]:
    """Parse Markdown, Q&A blocks, delimited pairs, bullets, and raw prose."""
    lines = text.splitlines()
    topic = "General"
    pending_image: tuple[str, str] | None = None
    units: list[SourceUnit] = []
    paragraph: list[str] = []
    paragraph_start_line = 0
    objective_block = False
    index = 0

    def source_at(line_number: int) -> str:
        return f"{source_name}:line-{line_number}"

    def flush_paragraph(line_number: int) -> None:
        nonlocal paragraph, paragraph_start_line, pending_image
        raw = " ".join(part.strip() for part in paragraph if part.strip()).strip()
        paragraph = []
        if not raw:
            return
        source_line = paragraph_start_line or line_number
        paragraph_start_line = 0
        for statement in split_sentences(raw):
            image_url, image_alt = pending_image or ("", "")
            units.extend(
                atomic_units(
                    SourceUnit(
                        text=statement,
                        topic=topic,
                        source=source_at(source_line),
                        image_url=image_url,
                        image_alt=image_alt,
                    )
                )
            )
            pending_image = None

    while index < len(lines):
        raw = lines[index]
        line = raw.strip()
        line_number = index + 1
        if not line:
            flush_paragraph(line_number)
            objective_block = False
            index += 1
            continue

        heading = _HEADING.match(line)
        if heading:
            flush_paragraph(line_number)
            topic = heading.group(1).strip()
            objective_block = False
            index += 1
            continue

        topic_match = _TOPIC_LINE.match(line)
        if topic_match:
            flush_paragraph(line_number)
            topic = topic_match.group(1).strip()
            index += 1
            continue

        if _OBJECTIVE_HEADER.match(line):
            flush_paragraph(line_number)
            objective_block = True
            index += 1
            continue

        if _OBJECTIVE_LINE.match(line) or (objective_block and _BULLET.match(raw)):
            flush_paragraph(line_number)
            index += 1
            continue
        objective_block = False

        image = _IMAGE_DIRECTIVE.match(line)
        if image:
            flush_paragraph(line_number)
            pending_image = (image.group("url").strip(), image.group("alt").strip())
            index += 1
            continue

        markdown_image = _IMAGE_MD.search(line)
        if markdown_image and markdown_image.group(0) == line:
            flush_paragraph(line_number)
            pending_image = (markdown_image.group(2), markdown_image.group(1).strip())
            index += 1
            continue

        question = _QA_LINE.match(line)
        if question:
            flush_paragraph(line_number)
            answer = ""
            extra = ""
            tags: list[str] = []
            lookahead = index + 1
            while lookahead < len(lines) and lines[lookahead].strip():
                candidate = lines[lookahead].strip()
                answer_match = _ANSWER_LINE.match(candidate)
                extra_match = _EXTRA_LINE.match(candidate)
                tags_match = _TAGS_LINE.match(candidate)
                if answer_match:
                    answer = answer_match.group(1).strip()
                elif extra_match:
                    extra = extra_match.group(1).strip()
                elif tags_match:
                    tags = parse_tags(tags_match.group(1))
                else:
                    break
                lookahead += 1
            if answer:
                image_url, image_alt = pending_image or ("", "")
                base = SourceUnit(
                    text=f"{question.group(1).strip()} {answer}",
                    question=question.group(1).strip(),
                    answer=answer,
                    extra=extra,
                    tags=tags,
                    topic=topic,
                    source=source_at(line_number),
                    image_url=image_url,
                    image_alt=image_alt,
                )
                units.extend(atomic_units(base))
                pending_image = None
                index = lookahead
                continue

        pair = parse_delimited_pair(line)
        if pair:
            flush_paragraph(line_number)
            image_url, image_alt = pending_image or ("", "")
            units.extend(
                atomic_units(
                    SourceUnit(
                        text=f"{pair[0]} {pair[1]}",
                        question=pair[0],
                        answer=pair[1],
                        topic=topic,
                        source=source_at(line_number),
                        image_url=image_url,
                        image_alt=image_alt,
                    )
                )
            )
            pending_image = None
            index += 1
            continue

        bullet = _BULLET.match(raw)
        if bullet:
            flush_paragraph(line_number)
            image_url, image_alt = pending_image or ("", "")
            units.extend(
                atomic_units(
                    SourceUnit(
                        text=bullet.group(1).strip(),
                        topic=topic,
                        source=source_at(line_number),
                        image_url=image_url,
                        image_alt=image_alt,
                    )
                )
            )
            pending_image = None
            index += 1
            continue

        if paragraph and starts_new_structured_line(paragraph[-1], line):
            flush_paragraph(line_number)
        if not paragraph:
            paragraph_start_line = line_number
        paragraph.append(line)
        index += 1

    flush_paragraph(len(lines) or 1)
    return [unit for unit in units if unit.text.strip() or unit.answer.strip()]


def starts_new_structured_line(previous: str, current: str) -> bool:
    """Separate note-like lines without breaking ordinary wrapped prose."""
    if re.search(r"(?:[A-Za-z][A-Za-z0-9_]*|\d+)\s*=\s*[^=]+$", previous):
        return True
    if previous.rstrip().endswith((".", "!", "?")) and re.match(r"^[A-Z0-9]", current):
        return True
    return bool(
        re.match(
            r"^(?:First|Second|Third|Finally|Before|After|Because|However|Unlike|"
            r"For example|An exception)\b",
            current,
            re.IGNORECASE,
        )
    )


def plan_knowledge(
    units: Sequence[SourceUnit], source_text: str, source_name: str
) -> tuple[list[LearningObjective], list[KnowledgeUnit]]:
    """Classify parsed units and connect them to explicit or inferred objectives."""
    explicit = extract_explicit_objectives(source_text, source_name)
    explicit_topics = {objective.topic for objective in explicit}
    inferred = infer_topic_objectives(
        (unit.topic for unit in units if unit.topic not in explicit_topics), source_name
    )
    objectives = [*explicit, *inferred]
    by_topic: dict[str, list[LearningObjective]] = defaultdict(list)
    for objective in objectives:
        by_topic[objective.topic].append(objective)

    knowledge_units: list[KnowledgeUnit] = []
    definitions_by_topic: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for unit in units:
        kind, purpose = classify_knowledge(unit.text, unit.question)
        unit_id = stable_id("unit", unit.text, unit.question, unit.answer, unit.source)
        objective_ids = assign_objectives(
            unit, by_topic.get(unit.topic) or by_topic.get("General", [])
        )
        prerequisites = [
            definition_id
            for term, definition_id in definitions_by_topic[unit.topic]
            if re.search(rf"\b{re.escape(term)}\b", unit.text, re.IGNORECASE)
        ]
        unit.knowledge_unit_id = unit_id
        unit.knowledge_kind = kind
        unit.learning_purpose = purpose
        unit.objective_ids = list(objective_ids)
        unit.prerequisite_ids = prerequisites
        knowledge = KnowledgeUnit(
            id=unit_id,
            text=unit.text,
            kind=kind,
            purpose=purpose,
            topic=unit.topic,
            source=unit.source,
            objective_ids=list(objective_ids),
            prerequisite_ids=prerequisites,
            origin=unit.origin,
            confidence=unit.confidence,
        )
        knowledge_units.append(knowledge)
        if kind == "definition":
            match = _DEFINITION.match(unit.text)
            term = definition_term(unit.question) if unit.question else ""
            term = term or (match.group("subject").strip() if match else "")
            if term:
                definitions_by_topic[unit.topic].append((term, unit_id))
    return objectives, knowledge_units


def assign_objectives(
    unit: SourceUnit, objectives: Sequence[LearningObjective]
) -> list[str]:
    if len(objectives) <= 1:
        return [objective.id for objective in objectives]
    unit_tokens = semantic_tokens(f"{unit.question} {unit.answer} {unit.text}")
    scored = [
        (len(unit_tokens & semantic_tokens(objective.label)), objective)
        for objective in objectives
    ]
    best = max((score for score, _ in scored), default=0)
    return [objective.id for score, objective in scored if score == best and score > 0]


def semantic_tokens(value: str) -> set[str]:
    stopwords = {
        "and", "the", "this", "that", "with", "from", "into", "what", "when",
        "where", "which", "able", "students", "learners", "explain", "identify",
        "understand", "describe", "apply",
    }
    return {
        token.casefold()
        for token in _WORDS.findall(value)
        if len(token) > 2 and token.casefold() not in stopwords
    }


def parse_delimited_pair(line: str) -> tuple[str, str] | None:
    for delimiter in (" :: ", "\t"):
        if delimiter in line:
            left, right = line.split(delimiter, 1)
            if left.strip() and right.strip():
                return left.strip(), right.strip()
    return None


def parse_tags(value: str) -> list[str]:
    return [slugify(tag) for tag in re.split(r"[,\s]+", value) if tag.strip()]


# Tokens that end with a period but do not end a sentence. Without this guard,
# "e.g.", "U.S.", "Fig. 3", and single-letter initials fragment ordinary prose.
_ABBREVIATIONS = frozenset(
    {
        "e.g", "i.e", "etc", "vs", "al", "cf", "approx", "no", "fig", "eq",
        "dr", "mr", "mrs", "ms", "prof", "st", "mt", "u.s", "u.k", "ph.d",
        "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct",
        "nov", "dec",
    }
)


def split_sentences(text: str) -> list[str]:
    """Split prose on sentence boundaries, skipping abbreviation periods."""
    parts: list[str] = []
    start = 0
    for boundary in _FACT_BOUNDARY.finditer(text):
        preceding = text[:boundary.start()].rstrip()
        token = re.search(r"(\S+)[.!?]+$", preceding)
        last = token.group(1).lower() if token else ""
        # Skip splitting after known abbreviations or single-letter initials.
        if last in _ABBREVIATIONS or re.fullmatch(r"[a-z]", last):
            continue
        segment = text[start:boundary.start()].strip()
        if segment:
            parts.append(segment)
        start = boundary.end()
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def atomic_units(unit: SourceUnit) -> list[SourceUnit]:
    """Split detectable enumerations and independent clauses into atomic units."""
    answer_or_text = unit.answer or unit.text
    list_match = _LIST_STATEMENT.match(answer_or_text)
    if list_match:
        items = split_list_items(list_match.group("items"))
        if len(items) >= 2:
            subject = list_match.group("subject").strip()
            verb = list_match.group("verb").strip()
            return [
                clone_unit(
                    unit,
                    text=f"{subject} {verb} {item}.",
                    question=f"What is component {position} of {len(items)} in {subject}?",
                    answer=item,
                    group_components=items,
                )
                for position, item in enumerate(items, start=1)
            ]

    answer_items = split_list_items(unit.answer) if unit.answer else []
    if len(answer_items) >= 2:
        label = re.sub(
            r"^(?:What are the components of|Which items make up)\s+",
            "",
            unit.question,
            flags=re.IGNORECASE,
        ).rstrip(" ?")
        label = re.sub(r"^What are (?:the )?", "", label, flags=re.IGNORECASE)
        label = re.sub(r"\s+named in the handout$", "", label, flags=re.IGNORECASE)
        return [
            clone_unit(
                unit,
                text=f"{unit.question} {item}",
                question=f"What is component {position} of {len(answer_items)} in {label}?",
                answer=item,
                group_components=answer_items,
            )
            for position, item in enumerate(answer_items, start=1)
        ]

    clauses = split_independent_clauses(unit.text)
    if len(clauses) > 1 and not unit.question:
        return [clone_unit(unit, text=clause) for clause in clauses]
    return [unit]


def clone_unit(unit: SourceUnit, **changes: object) -> SourceUnit:
    values = asdict(unit)
    values.update(changes)
    return SourceUnit(**values)


def split_list_items(text: str) -> list[str]:
    if not text or not re.search(r"[,;]", text):
        return []
    if ";" in text:
        items = [part.strip(" .") for part in text.split(";") if part.strip(" .")]
    else:
        normalized = re.sub(r",?\s+(?:and|or)\s+", ", ", text, flags=re.IGNORECASE)
        items = [part.strip(" .") for part in normalized.split(",") if part.strip(" .")]
    if len(items) < 2 or any(word_count(item) > 12 for item in items):
        return []
    return items


def enumerated_components(text: str) -> list[str]:
    """Return the set members when a back is a short enumeration, else ``[]``.

    Both the generator (to attach a mnemonic) and the validator (to demand one)
    call this, so they never disagree about what counts as a >=3-component set.
    Clausal compounds joined by ``whereas``/``but``/... are not enumerations; a
    member that contains a verb is a clause, not a set element.
    """
    clean = strip_html_and_cloze(text).strip(" .")
    if re.search(r"\b(?:whereas|while|because|however|therefore|but)\b", clean, re.I):
        return []
    items = split_list_items(clean)
    if any(_VERB.search(item) for item in items):
        return []
    return items


def split_independent_clauses(text: str) -> list[str]:
    if re.search(
        r"\b(?:but|whereas|while|however|therefore|because|evidence|claim|exception)\b",
        text,
        re.IGNORECASE,
    ):
        return [text.strip()]
    semicolon_parts = [part.strip(" .") for part in text.split(";") if part.strip(" .")]
    if len(semicolon_parts) > 1 and all(_VERB.search(part) for part in semicolon_parts):
        return [part + "." for part in semicolon_parts]
    parts = re.split(r"\s+and\s+", text, flags=re.IGNORECASE)
    if len(parts) == 2 and all(word_count(part) >= 3 and _VERB.search(part) for part in parts):
        return [part.strip(" .") + "." for part in parts]
    return [text.strip()]


def build_cards(units: Sequence[SourceUnit]) -> list[Card]:
    cards: list[Card] = []
    type_counts: Counter[str] = Counter()
    for index, unit in enumerate(units):
        card_type = choose_card_type(unit, index, type_counts)
        front, back = render_prompt(unit, card_type)
        if not front.strip() or not back.strip():
            continue
        mnemonic = make_mnemonic(unit.group_components or enumerated_components(back))
        image_url = unit.image_url
        image_alt = normalize_image_alt(unit.image_alt) if image_url else ""
        if image_url:
            card_type = "image-supported"
            back = (
                f'{back}<br><img src="{html.escape(image_url, quote=True)}" '
                f'alt="{html.escape(image_alt, quote=True)}">'
            )
        extra = build_extra(unit, front, back)
        tags = [*unit.tags, slugify(unit.topic), "auto"]
        card_id = stable_card_id(front, back, unit.source)
        card = Card(
            front=front,
            back=back,
            extra=extra,
            mnemonic=mnemonic,
            card_type=card_type,
            tags=tags,
            topic=unit.topic,
            source=unit.source,
            image_url=image_url,
            image_alt=image_alt,
            card_id=card_id,
            knowledge_unit_id=unit.knowledge_unit_id,
            knowledge_kind=unit.knowledge_kind,
            learning_purpose=unit.learning_purpose,
            objective_ids=list(unit.objective_ids),
            prerequisite_ids=list(unit.prerequisite_ids),
            origin=unit.origin,
            confidence=unit.confidence,
        )
        cards.append(card)
        type_counts[card_type] += 1

    return cards


def choose_card_type(unit: SourceUnit, index: int, counts: Counter[str]) -> str:
    if unit.image_url:
        return "image-supported"
    if unit.knowledge_kind == "formula" or exact_answer_candidate(unit.answer):
        return "typed"
    if unit.question:
        if reversible_definition(unit) and counts["reverse"] <= counts["qa"] // 2:
            return "reverse"
        return "qa"
    if unit.knowledge_kind in {"definition", "comparison", "mechanism", "argument", "narrative", "exception"}:
        return "qa"
    return "cloze" if meaningful_cloze_candidate(unit.text) else "qa"


def exact_answer_candidate(answer: str) -> bool:
    if not answer:
        return False
    value = answer.strip().rstrip(".")
    return bool(
        re.fullmatch(r"[A-Za-z]\w*\s*=\s*.+", value)
        or (word_count(value) <= 3 and re.search(r"\d", value))
        or re.fullmatch(r"[A-Z]{2,}", value)
    )


def meaningful_cloze_candidate(text: str) -> bool:
    relation = _RELATION.match(text)
    if not relation:
        return False
    answer = relation.group("object").strip(" .")
    return 1 <= word_count(answer) <= 8


def reversible_definition(unit: SourceUnit) -> bool:
    if unit.question and unit.answer:
        return word_count(unit.answer) <= 12 and bool(definition_term(unit.question))
    return bool(_DEFINITION.match(unit.text))


def render_prompt(unit: SourceUnit, card_type: str) -> tuple[str, str]:
    if card_type == "reverse" and unit.question and unit.answer:
        term = definition_term(unit.question)
        if term:
            return f"Which term means: {unit.answer.rstrip('.')}?", term
    if card_type == "cloze":
        cloze = make_cloze(unit.text)
        return cloze, answer_from_cloze(cloze)
    if unit.question and unit.answer:
        return unit.question, unit.answer
    formula = re.match(r"^(?P<label>[^=]{1,60}?)\s*=\s*(?P<formula>.+?)\.?$", unit.text)
    if formula:
        return f"What is the formula for {formula.group('label').strip()}?", formula.group("formula").strip()
    semantic = render_semantic_prompt(unit)
    if semantic:
        return semantic
    definition = _DEFINITION.match(unit.text)
    if definition:
        return f"What is {definition.group('subject').strip()}?", definition.group("object").strip(" .")
    relation = _RELATION.match(unit.text)
    if relation:
        subject = relation.group("subject").strip()
        verb = relation.group("verb").lower()
        object_ = relation.group("object").strip(" .")
        return f"Complete: {subject} {verb} ___.", object_
    # Defer, don't fake. If no specific prompt can be rendered, emit nothing so
    # the unit surfaces as deferred (see main) for an authoring pass, rather than
    # shipping a generic "what does the source say about X" card the rubric would
    # only flag. The deterministic path authors what it can verify; prose it
    # cannot parse is handed to the LLM/human author.
    return ("", "")


def render_semantic_prompt(unit: SourceUnit) -> tuple[str, str] | None:
    text = unit.text.strip(" .")
    if unit.knowledge_kind == "comparison":
        match = re.match(
            r"^(?P<left>.+?) differs? from (?P<right>.+?) (?:because|by) (?P<criterion>.+)$",
            text,
            re.IGNORECASE,
        )
        if match:
            return (
                f"How does {match.group('left')} differ from {match.group('right')}?",
                match.group("criterion"),
            )
    if unit.knowledge_kind == "mechanism":
        match = re.match(r"^Because (?P<cause>.+?), (?P<result>.+)$", text, re.IGNORECASE)
        if match:
            return (
                f"What causes this outcome: {match.group('result').rstrip('.')}?",
                match.group("cause"),
            )
    if unit.knowledge_kind == "narrative":
        match = re.match(r"^After (?P<event>.+?), (?P<result>.+)$", text, re.IGNORECASE)
        if match:
            return f"What happens after {match.group('event')}?", match.group("result")
    if unit.knowledge_kind == "exception":
        match = re.match(r"^(?P<rule>.+?) only when (?P<condition>.+)$", text, re.IGNORECASE)
        if match:
            return (
                f"Under what condition is this rule true: {match.group('rule')}?",
                match.group("condition"),
            )
    return None


# Stems of low-specificity prompts that recall "what the source says" rather
# than a concrete fact. The deterministic generator no longer emits these (it
# defers such units instead), but the auditor keeps the guard so an authored CSV
# that reintroduces them is caught.
_GENERIC_PROMPT_STEMS = (
    "What distinction does the source make",
    "What sequence does the source give",
    "Which procedure step is described",
    "What mechanism does the source explain",
    "What claim or evidence is presented",
    "Which event or causal link occurs",
    "Which example illustrates a concept",
    "Which exception or qualification applies",
    "What does the source state about",
    "What fact should you recall about",
)
_GENERIC_PROMPT = re.compile("|".join(re.escape(stem) for stem in _GENERIC_PROMPT_STEMS))


def is_generic_prompt(front: str) -> bool:
    """True for vague prompts that test no specific fact (audit guard)."""
    return bool(_GENERIC_PROMPT.match(strip_html_and_cloze(front).strip()))


def make_cloze(statement: str) -> str:
    if _CLOZE.search(statement):
        return statement
    definition = _DEFINITION.match(statement)
    if definition:
        return (
            f"{definition.group('subject').strip()} is "
            f"{{{{c1::{definition.group('object').strip(' .')}}}}}."
        )
    verb = _VERB.search(statement)
    if verb:
        start = verb.end()
        answer = statement[start:].strip(" .")
        if answer:
            return f"{statement[:start]} {{{{c1::{answer}}}}}."
    words = statement.strip(" .").split()
    if len(words) >= 3:
        answer = " ".join(words[-min(4, len(words) - 1):])
        prefix = " ".join(words[:-min(4, len(words) - 1)])
        return f"{prefix} {{{{c1::{answer}}}}}."
    return statement


def answer_from_cloze(cloze: str) -> str:
    answers = _CLOZE.findall(cloze)
    return "; ".join(answers) if answers else cloze


def definition_term(question: str) -> str:
    for pattern in (_WHAT_IS, _DEFINE, _WHAT_MEANS):
        match = pattern.match(question.strip())
        if match:
            term = match.group("term").strip(" .?")
            if re.match(r"^(?:answer\s+)?component\b", term, re.IGNORECASE):
                return ""
            return term
    return ""


def build_extra(unit: SourceUnit, front: str = "", back: str = "") -> str:
    """Compose the Extra field from any explicit elaboration plus context.

    Prefers an author-supplied ``Extra:``. Without one, it falls back to the
    declarative statement rather than echoing the question, so a Q&A unit does
    not produce ``Explanation: <question> <answer>``. Whether the explanation is
    substantive is judged separately by ``explanation_is_thin`` at validation.
    The context trigger uses the rendered ``front``/``back`` so it matches the
    fields the validator inspects.
    """
    explanation = unit.extra.strip() or declarative_statement(unit)
    parts = [f"Explanation: {explanation}"]
    if requires_context(front or unit.text, back or unit.question):
        parts.append(f"Context: {unit.topic} background is assumed; review {unit.source} if unfamiliar.")
    else:
        parts.append(f"Context: Topic: {unit.topic}.")
    return " ".join(parts)


def declarative_statement(unit: SourceUnit) -> str:
    """A statement form of a unit that does not restate the question verbatim."""
    if unit.question and unit.answer:
        answer = unit.answer.strip()
        return answer if answer.endswith((".", "!", "?")) else f"{answer}."
    return unit.text.strip()


def explanation_is_thin(card: Card) -> bool:
    """True when the explanation adds no information beyond Front and Back.

    A restated prompt gives false confidence: the ``pre_understanding`` audit
    check only verifies the ``Explanation:`` prefix exists. This flags cards
    whose explanation is a near-duplicate of the prompt so a human (or an LLM
    pass) enriches them before study.
    """
    body = card.extra
    if body.startswith("Explanation:"):
        body = body[len("Explanation:"):]
    body = body.split("Context:", 1)[0]
    explanation_tokens = semantic_tokens(body)
    if not explanation_tokens:
        return True
    prompt_tokens = semantic_tokens(f"{card.front} {card.back}")
    return explanation_tokens <= prompt_tokens


def requires_context(*values: str) -> bool:
    text = " ".join(values)
    return bool(_TECHNICAL.search(text) or re.search(r"\b[A-Za-z]+\d+\b", text))


def make_mnemonic(components: Sequence[str]) -> str:
    if len(components) < 3:
        return ""
    initials = "".join(first_alnum(component) for component in components)
    labels = ", ".join(components)
    return f"{initials.upper()}: {labels}"


def first_alnum(value: str) -> str:
    match = re.search(r"[A-Za-z0-9]", value)
    return match.group(0) if match else "X"


def normalize_image_alt(alt: str) -> str:
    alt = alt.strip()
    if not alt:
        return ""
    if re.search(r"\b(?:recall|remember|cue|anchor|distinguish|shows why)\b", alt, re.I):
        return alt
    return f"{alt}; this visual cue anchors the relationship tested by the card."


def stable_card_id(front: str, back: str, source: str) -> str:
    digest = hashlib.sha256(f"{front}\0{back}\0{source}".encode()).hexdigest()
    return digest[:16]


def interleave_cards(cards: Sequence[Card], seed: int = DEFAULT_SEED) -> list[Card]:
    """Shuffle within topics, then avoid adjacent same-topic cards when possible."""
    rng = random.Random(seed)
    grouped: dict[str, deque[Card]] = defaultdict(deque)
    for topic, topic_cards in group_by_topic(cards).items():
        topic_cards = list(topic_cards)
        rng.shuffle(topic_cards)
        grouped[topic].extend(topic_cards)

    result: list[Card] = []
    last_topic = ""
    while grouped:
        candidates = [topic for topic in grouped if topic != last_topic] or list(grouped)
        max_size = max(len(grouped[topic]) for topic in candidates)
        largest = [topic for topic in candidates if len(grouped[topic]) == max_size]
        topic = rng.choice(largest)
        result.append(grouped[topic].popleft())
        last_topic = topic
        if not grouped[topic]:
            del grouped[topic]
    return result


def group_by_topic(cards: Sequence[Card]) -> dict[str, list[Card]]:
    groups: dict[str, list[Card]] = defaultdict(list)
    for card in cards:
        groups[card.topic].append(card)
    return groups


def validate_card(card: Card) -> list[Violation]:
    violations: list[Violation] = []
    if not card.front.strip() or not card.back.strip():
        violations.append(error("MISSING_CONTENT", "Front and Back are required.", card, "Add a single unambiguous prompt and answer."))
    if not card.source.strip():
        violations.append(error("MISSING_SOURCE", "Assessed content requires source provenance.", card, "Add a page, slide, section, or line source."))
    if card.origin == "generated-enrichment" and "Enrichment:" not in card.extra:
        violations.append(error("UNLABELED_ENRICHMENT", "Generated enrichment is not visibly labeled.", card, "Prefix generated examples or practice with 'Enrichment:'."))
    if card.origin == "inferred" and "Inference:" not in card.extra:
        violations.append(warning("UNLABELED_INFERENCE", "Inferred content should be distinguished from direct source claims.", card, "Add an 'Inference:' label or mark the unit as source-supported."))
    if not 0 <= card.confidence <= 1:
        violations.append(error("INVALID_CONFIDENCE", "Confidence must be between 0 and 1.", card, "Set semantic confidence in the inclusive 0..1 range."))
    if card.knowledge_kind not in KNOWLEDGE_KINDS:
        violations.append(error("INVALID_KNOWLEDGE_KIND", f"Unknown knowledge kind {card.knowledge_kind!r}.", card, "Use a supported domain-neutral knowledge kind."))
    if card.learning_purpose not in LEARNING_PURPOSES:
        violations.append(error("INVALID_LEARNING_PURPOSE", f"Unknown learning purpose {card.learning_purpose!r}.", card, "Use a supported learning purpose."))
    if card.origin not in ORIGINS:
        violations.append(error("INVALID_ORIGIN", f"Unknown origin {card.origin!r}.", card, "Use source, inferred, or generated-enrichment."))
    if word_count(card.front) > MAX_FRONT_WORDS:
        violations.append(error("FRONT_TOO_LONG", f"Front has {word_count(card.front)} words; maximum is {MAX_FRONT_WORDS}.", card, "Shorten or split the prompt."))
    if not card.extra.startswith("Explanation:"):
        violations.append(error("MISSING_EXPLANATION", "Extra must begin with an explanation.", card, "Add pre-understanding context in Extra."))
    if requires_context(card.front, card.back) and "Context:" not in card.extra:
        violations.append(error("MISSING_CONTEXT", "Technical card lacks a Context section.", card, "Add the prerequisite domain context."))
    if card.card_type not in CARD_TYPES:
        violations.append(error("INVALID_CARD_TYPE", f"Unknown card type {card.card_type!r}.", card, f"Use one of: {', '.join(CARD_TYPES)}."))
    if card.card_type == "cloze" and not _CLOZE.search(card.front):
        violations.append(error("CLOZE_FORMAT", "Cloze card does not contain Anki cloze syntax.", card, "Add one {{c1::answer}} deletion or change CardType."))
    if card.card_type != "cloze" and _CLOZE.search(card.front):
        violations.append(error("TYPE_FORMAT_MISMATCH", f"{card.card_type} card contains cloze syntax.", card, "Render a direct prompt or set CardType to cloze."))
    if card.card_type == "reverse" and not card.front.startswith("Which term means:"):
        violations.append(error("REVERSE_FORMAT", "Reverse card is not a term-from-definition prompt.", card, "Render 'Which term means: <definition>?' or change CardType."))
    component_count = estimate_components(card.back)
    if component_count > MAX_COMPONENTS:
        violations.append(error("COGNITIVE_LOAD", f"Back appears to contain {component_count} components.", card, "Split into atomic cards with at most four components."))
    if looks_compound(card.back):
        violations.append(warning("ATOMICITY_REVIEW", "Back may contain more than one independently testable fact.", card, "Split independent clauses or confirm they form one fact."))
    if len(enumerated_components(card.back)) >= 3 and not card.mnemonic.strip():
        violations.append(error("MISSING_MNEMONIC", "A set of at least three components lacks a mnemonic.", card, "Add an acronym or visual association."))
    if is_generic_prompt(card.front):
        violations.append(warning("GENERIC_PROMPT", "Prompt recalls 'what the source says' rather than a specific fact.", card, "Rewrite as a concrete question testing one fact, or defer the unit."))
    if explanation_is_thin(card):
        violations.append(warning("THIN_EXPLANATION", "Explanation restates the prompt without adding understanding.", card, "Add why the fact holds, or a distinguishing detail, before study."))
    if card.image_url:
        if card.card_type != "image-supported":
            violations.append(error("IMAGE_TYPE", "Image card is not marked image-supported.", card, "Set CardType to image-supported."))
        if not image_alt_is_explanatory(card.image_alt):
            violations.append(error("IMAGE_ALT", "Image alt text does not explain its recall value.", card, "Describe what the image cues and why it aids recall."))
    return violations


def estimate_components(text: str) -> int:
    clean = strip_html_and_cloze(text)
    if not re.search(r"[,;]", clean):
        return 1
    return max(1, len([part for part in re.split(r"[,;]", clean) if part.strip()]))


def looks_compound(text: str) -> bool:
    clean = strip_html_and_cloze(text)
    clauses = re.split(r";|\s+(?:and|but|whereas|while)\s+", clean, flags=re.I)
    return len(clauses) > 1 and sum(bool(_VERB.search(part)) for part in clauses) > 1


def image_alt_is_explanatory(alt: str) -> bool:
    return bool(
        word_count(alt) >= 6
        and re.search(r"\b(?:recall|remember|cue|anchor|distinguish|relationship|spatial)\b", alt, re.I)
    )


def validate_deck(cards: Sequence[Card], config: GenerationConfig) -> list[Violation]:
    violations = [violation for card in cards for violation in validate_card(card)]
    if not cards:
        violations.append(Violation("error", "EMPTY_DECK", "No independently gradable cards could be generated.", action="Add explicit facts, questions, relations, or structured source material."))
    if config.new_cards_per_day > 20:
        violations.append(Violation("error", "DAILY_LIMIT", f"New cards/day is {config.new_cards_per_day}; maximum is 20.", action="Set --new-cards-per-day to 20 or fewer."))
    if config.graduating_interval_days != 3:
        violations.append(Violation("warning", "GRADUATING_INTERVAL", "Graduating interval differs from the requested 3-day baseline.", action="Use --graduating-interval 3 unless intentionally overridden."))
    if config.easy_interval_days != 7:
        violations.append(Violation("warning", "EASY_INTERVAL", "Easy interval differs from the requested 7-day baseline.", action="Use --easy-interval 7 unless intentionally overridden."))
    if config.max_ease_percent > 250:
        violations.append(Violation("error", "EASE_CAP", "Maximum ease exceeds 250%.", action="Set --max-ease to 250 or lower."))
    if config.starting_ease_percent > config.max_ease_percent:
        violations.append(Violation("error", "STARTING_EASE", "Starting ease exceeds the configured ease cap.", action="Set starting ease at or below max ease."))
    if config.easy_button_policy != "avoid":
        violations.append(Violation("error", "EASY_POLICY", "Easy-button policy must remain 'avoid' for this rubric.", action="Set easy_button_policy to avoid."))
    if config.scheduler == "fsrs" and any(step_uses_day(step) for step in config.learning_steps):
        violations.append(Violation("error", "FSRS_LONG_STEP", "FSRS profile contains a learning step of one day or longer.", action="Use sub-day steps with FSRS, or select legacy-sm2 for the 10m 1d policy."))
    if config.interleave_topics and has_avoidable_topic_runs(cards):
        violations.append(Violation("warning", "INTERLEAVING", "Adjacent same-topic cards remain where another topic was available.", action="Regenerate with topic interleaving enabled."))
    return violations


def step_uses_day(step: str) -> bool:
    match = re.fullmatch(r"(\d+)([mhd])", step.strip().lower())
    if not match:
        return True
    amount, unit = int(match.group(1)), match.group(2)
    return unit == "d" or (unit == "h" and amount >= 24)


def has_avoidable_topic_runs(cards: Sequence[Card]) -> bool:
    if len({card.topic for card in cards}) < 2:
        return False
    remaining = Counter(card.topic for card in cards)
    for previous, current in zip(cards, cards[1:]):
        remaining[previous.topic] -= 1
        if previous.topic == current.topic and any(
            count > 0 for topic, count in remaining.items() if topic != current.topic
        ):
            return True
    return False


def error(code: str, message: str, card: Card, action: str) -> Violation:
    return Violation("error", code, message, card.card_id, action)


def warning(code: str, message: str, card: Card, action: str) -> Violation:
    return Violation("warning", code, message, card.card_id, action)


def write_csv(cards: Sequence[Card], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(card.to_row() for card in cards)


def write_json(data: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def analyze_retention(path: Path) -> dict[str, object]:
    """Compare predicted and actual recall for review rows with interval >21d."""
    mature: list[dict[str, object]] = []
    if not path.exists():
        return {"status": "not-provided", "mature_reviews": 0, "rows": []}
    with path.open(encoding="utf-8", newline="") as handle:
        for line_number, row in enumerate(csv.DictReader(handle), start=2):
            try:
                interval = float(row.get("interval_days", ""))
                predicted = float(row.get("predicted_retention", ""))
                actual = float(row.get("actual_recalled", ""))
            except (TypeError, ValueError):
                mature.append({"line": line_number, "error": "invalid numeric retention row"})
                continue
            if interval <= 21:
                continue
            mature.append(
                {
                    "card_id": row.get("card_id", ""),
                    "interval_days": interval,
                    "predicted_retention": predicted,
                    "actual_recalled": actual,
                    "calibration_error": round(actual - predicted, 4),
                }
            )
    valid = [row for row in mature if "calibration_error" in row]
    mean_error = (
        round(sum(float(row["calibration_error"]) for row in valid) / len(valid), 4)
        if valid
        else None
    )
    return {"status": "ok", "mature_reviews": len(valid), "mean_calibration_error": mean_error, "rows": mature}


def parse_steps(value: str) -> tuple[str, ...]:
    steps = tuple(part for part in re.split(r"[,\s]+", value.strip()) if part)
    if not steps or not all(re.fullmatch(r"\d+[mhd]", step.lower()) for step in steps):
        raise argparse.ArgumentTypeError("steps must look like '10m 1d' or '10m,1d'")
    return steps


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Text or Markdown source file.")
    parser.add_argument("--output", type=Path, required=True, help="Output Anki-compatible CSV.")
    parser.add_argument("--learning-steps", type=parse_steps, default=("10m", "1d"))
    parser.add_argument("--graduating-interval", type=int, default=3)
    parser.add_argument("--easy-interval", type=int, default=7)
    parser.add_argument("--starting-ease", type=int, default=250)
    parser.add_argument("--max-ease", type=int, default=250)
    parser.add_argument("--new-cards-per-day", type=int, default=20)
    parser.add_argument("--scheduler", choices=("legacy-sm2", "fsrs"), default="legacy-sm2")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--retention-log", type=Path, help="Optional review CSV for the >21-day retention hook.")
    parser.add_argument("--allow-violations", action="store_true", help="Exit zero even when rubric errors remain.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.input.exists():
        print(f"Input does not exist: {args.input}", file=sys.stderr)
        return 2
    config = GenerationConfig(
        learning_steps=args.learning_steps,
        graduating_interval_days=args.graduating_interval,
        easy_interval_days=args.easy_interval,
        starting_ease_percent=args.starting_ease,
        max_ease_percent=args.max_ease,
        new_cards_per_day=args.new_cards_per_day,
        scheduler=args.scheduler,
        seed=args.seed,
    )
    source_text = args.input.read_text(encoding="utf-8")
    units = parse_content(source_text, args.input.name)
    objectives, knowledge_units = plan_knowledge(units, source_text, args.input.name)
    cards = build_cards(units)
    if config.interleave_topics:
        cards = interleave_cards(cards, config.seed)
    violations = validate_deck(cards, config)

    write_csv(cards, args.output)
    settings_path = args.output.with_suffix(".settings.json")
    violations_path = args.output.with_suffix(".violations.json")
    retention_path = args.output.with_suffix(".retention.json")
    manifest_path = args.output.with_suffix(".manifest.json")
    coverage_path = args.output.with_suffix(".coverage.json")
    represented = {card.knowledge_unit_id for card in cards if card.knowledge_unit_id}
    for unit in knowledge_units:
        if unit.id not in represented:
            unit.status = "deferred"
    settings = {
        **asdict(config),
        "learning_steps": list(config.learning_steps),
        "portable_easy_button_enforcement": False,
        "note": "CSV import cannot disable Anki's Easy button; 'avoid' is a review policy.",
    }
    write_json(settings, settings_path)
    write_json([asdict(violation) for violation in violations], violations_path)
    write_json(analyze_retention(args.retention_log) if args.retention_log else {"status": "not-provided", "mature_reviews": 0, "rows": []}, retention_path)
    write_json(
        {
            "version": 1,
            "source": args.input.name,
            "objectives": [objective.to_dict() for objective in objectives],
            "knowledge_units": [unit.to_dict() for unit in knowledge_units],
        },
        manifest_path,
    )
    coverage_report = build_coverage_report(objectives, knowledge_units)
    write_json(coverage_report, coverage_path)

    errors = sum(violation.level == "error" for violation in violations)
    warnings = sum(violation.level == "warning" for violation in violations)
    deferred = sum(unit.status == "deferred" for unit in knowledge_units)
    coverage_summary = coverage_report["summary"]
    print(f"Generated {len(cards)} cards; deferred {deferred} unit(s): {args.output}")
    if deferred:
        print(
            f"Author the {deferred} deferred unit(s) listed in {manifest_path} "
            "(status=deferred); the deterministic path only renders units it can "
            "ground specifically."
        )
    print(
        "Objectives: "
        f"{coverage_summary['covered_objectives']}/{coverage_summary['objectives']} covered"
    )
    print(f"Rubric: {errors} error(s), {warnings} warning(s): {violations_path}")
    print(f"Manifest: {manifest_path}")
    print(f"Coverage: {coverage_path}")
    print(f"Settings: {settings_path}")
    return 0 if args.allow_violations or errors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
