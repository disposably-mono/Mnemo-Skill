"""Parse source notes into semantic units and knowledge plans."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict
from typing import Sequence

from mnemo.core.knowledge import (
    KnowledgeUnit,
    LearningObjective,
    classify_knowledge,
    extract_explicit_objectives,
    infer_topic_objectives,
    objective_label,
    stable_id,
)
from mnemo.core.verbatim import (
    fenced_code_opening,
    is_display_math_delimiter,
    is_fenced_code_closing,
    is_single_line_display_math,
)

from .models import SourceUnit
from .patterns import (
    _ANSWER_LINE,
    _BULLET,
    _DEFINITION,
    _EXTRA_LINE,
    _HEADING,
    _IMAGE_DIRECTIVE,
    _IMAGE_MD,
    _LIST_STATEMENT,
    _OBJECTIVE_HEADER,
    _QA_LINE,
    _TAGS_LINE,
    _TOPIC_LINE,
)
from .text import (
    definition_term,
    parse_delimited_pair,
    parse_tags,
    semantic_tokens,
    split_independent_clauses,
    split_list_items,
    split_sentences,
    word_count,
)

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
        code_opening = fenced_code_opening(raw)
        if code_opening:
            flush_paragraph(line_number)
            marker, language = code_opening
            closing_index = index + 1
            while closing_index < len(lines) and not is_fenced_code_closing(
                lines[closing_index], marker
            ):
                closing_index += 1
            if closing_index < len(lines):
                image_url, image_alt = pending_image or ("", "")
                units.append(
                    SourceUnit(
                        text="\n".join(lines[index + 1:closing_index]),
                        topic=topic,
                        source=source_at(line_number),
                        image_url=image_url,
                        image_alt=image_alt,
                        verbatim_kind="code",
                        verbatim_language=language,
                    )
                )
                pending_image = None
                index = closing_index + 1
                continue
            units.append(
                SourceUnit(
                    text="\n".join(lines[index + 1:]),
                    topic=topic,
                    source=source_at(line_number),
                    verbatim_kind="code",
                    verbatim_language=language,
                )
            )
            index = len(lines)
            continue

        if is_single_line_display_math(raw):
            flush_paragraph(line_number)
            image_url, image_alt = pending_image or ("", "")
            units.append(
                SourceUnit(
                    text=line,
                    topic=topic,
                    source=source_at(line_number),
                    image_url=image_url,
                    image_alt=image_alt,
                    verbatim_kind="math",
                )
            )
            pending_image = None
            index += 1
            continue

        if is_display_math_delimiter(raw):
            flush_paragraph(line_number)
            closing_index = index + 1
            while closing_index < len(lines) and not is_display_math_delimiter(
                lines[closing_index]
            ):
                closing_index += 1
            if closing_index < len(lines):
                image_url, image_alt = pending_image or ("", "")
                units.append(
                    SourceUnit(
                        text="\n".join(lines[index:closing_index + 1]),
                        topic=topic,
                        source=source_at(line_number),
                        image_url=image_url,
                        image_alt=image_alt,
                        verbatim_kind="math",
                    )
                )
                pending_image = None
                index = closing_index + 1
                continue
            units.append(
                SourceUnit(
                    text="\n".join(lines[index:]),
                    topic=topic,
                    source=source_at(line_number),
                    verbatim_kind="math",
                )
            )
            index = len(lines)
            continue

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

        if objective_label(line, raw, in_block=objective_block) is not None:
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
                units.append(base)
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
        if unit.verbatim_kind:
            kind, purpose = "fact", "recall"
        else:
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


# A comma is a thousands separator, not an enumeration delimiter, when it sits
# between digits at a group boundary (e.g. "300,000" or "1,234,567,890,123").
# Protect those commas before splitting so numeric answers survive intact.
