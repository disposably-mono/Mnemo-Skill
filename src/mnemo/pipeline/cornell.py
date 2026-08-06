"""Render source text into Mnemo's Cornell note contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Sequence

from mnemo.pipeline.flashcards.authoring import (
    AiAuthoringError,
    CommandAiProvider,
    FileAiProvider,
    evidence_is_supported,
    normalize_evidence,
    parse_ai_payload,
)
from mnemo.pipeline.flashcards.cli import selected_source_text
from mnemo.pipeline.flashcards.parse import parse_content, plan_knowledge
from mnemo.pipeline.flashcards.policy import CANDIDATE_CARDS_SECTION
from mnemo.pipeline.flashcards.render import (
    answer_exceeds_component_limit,
    build_cards,
    render_prompt,
)
from mnemo.pipeline.flashcards.validate import validate_deck
from mnemo.pipeline.flashcards.models import GenerationConfig, SourceUnit
from mnemo.pipeline.flashcards.text import slugify


def validate_scalar(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    if any(character in value for character in "\r\n\t"):
        raise ValueError(f"{name} must not contain control characters")


def yaml_scalar(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_. -]+", value):
        return value
    return json.dumps(value)


def markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Text or Markdown source file.")
    parser.add_argument("--output", type=Path, required=True, help="Output .cornell.md file.")
    parser.add_argument("--course-slug", default="course-slug")
    parser.add_argument("--module-slug", default="module-slug")
    parser.add_argument("--title", default="Module")
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--author", choices=("deterministic", "ai"), default="deterministic")
    parser.add_argument(
        "--ai-response-file",
        type=Path,
        help="Read structured Cornell JSON from a file.",
    )
    parser.add_argument(
        "--ai-command",
        help="Command that reads the Cornell prompt on stdin and writes JSON to stdout.",
    )
    return parser


def render_cornell_note(
    source_text: str,
    source_name: str,
    *,
    course_slug: str,
    module_slug: str,
    title: str,
    tags: Sequence[str],
) -> str:
    validate_scalar(source_name, "source name")
    validate_scalar(course_slug, "course slug")
    validate_scalar(module_slug, "module slug")
    validate_scalar(title, "title")
    for tag in tags:
        validate_scalar(tag, "tag")
    units = parse_content(source_text, source_name)
    plan_knowledge(units, source_text, source_name)
    note_tags = list(dict.fromkeys([*tags, course_slug, module_slug]))
    cards = candidate_cards(units, note_tags)
    if not cards:
        raise ValueError("no candidate cards could be generated from this source")
    cues = "\n".join(
        f"| {markdown_cell(front)} | {markdown_cell(back)} |"
        for front, back, _, _ in cards[:8]
    )
    card_blocks = "\n\n".join(
        "\n".join(
            [
                f"Q: {front}",
                f"A: {back}",
                f"Extra: {extra}",
                f"Tags: {' '.join(card_tags)}",
            ]
        )
        for front, back, extra, card_tags in cards
    )
    return (
        "---\n"
        f"courseSlug: {yaml_scalar(course_slug)}\n"
        f"moduleSlug: {yaml_scalar(module_slug)}\n"
        f"noteDate: {date.today().isoformat()}\n"
        "sourceFiles:\n"
        f"  - {yaml_scalar(source_name)}\n"
        "tags:\n"
        + "".join(f"  - {yaml_scalar(tag)}\n" for tag in note_tags)
        + "---\n\n"
        f"# {title} Cornell Notes\n\n"
        "## Source References\n\n"
        f"- `{source_name}`\n\n"
        "## Cues\n\n"
        "| Cue | Notes |\n"
        "| --- | --- |\n"
        f"{cues}\n\n"
        "## Notes\n\n"
        f"{compact_notes(source_text)}\n\n"
        "## Summary\n\n"
        f"{compact_summary(source_text)}\n\n"
        "## Follow-Up Gaps\n\n"
        "- Review generated candidate cards against the source before import.\n\n"
        f"## {CANDIDATE_CARDS_SECTION}\n\n"
        f"{card_blocks}\n"
    )


def candidate_cards(
    units: Sequence[object], base_tags: Sequence[str]
) -> list[tuple[str, str, str, list[str]]]:
    cards: list[tuple[str, str, str, list[str]]] = []
    for unit in units:
        answer = getattr(unit, "answer", "")
        if answer and answer_exceeds_component_limit(answer):
            continue
        front, back = render_prompt(unit, "qa")
        if not front.strip() or not back.strip():
            continue
        extra = (
            getattr(unit, "extra", "")
            or f"Source-grounded in {getattr(unit, 'source', 'source')}."
        )
        tags = list(dict.fromkeys([*base_tags, slugify(getattr(unit, "topic", "general"))]))
        candidate = (front, back.rstrip("."), extra, tags)
        if candidate_is_valid(candidate):
            cards.append(candidate)
    return cards


def candidate_is_valid(candidate: tuple[str, str, str, list[str]]) -> bool:
    front, back, extra, tags = candidate
    block = (
        f"## {CANDIDATE_CARDS_SECTION}\n\n"
        + "\n".join(
            [
                f"Q: {front}",
                f"A: {back}",
                f"Extra: {extra}",
                f"Tags: {' '.join(tags)}",
            ]
        )
    )
    units = parse_content(block, "candidate.md")
    plan_knowledge(units, block, "candidate.md")
    cards = build_cards(units)
    return bool(cards) and not [
        violation
        for violation in validate_deck(cards, GenerationConfig(interleave_topics=False))
        if violation.level == "error"
    ]


def validate_contract(note: str, source_name: str) -> None:
    candidate_text = selected_source_text(note, Path(source_name), CANDIDATE_CARDS_SECTION)
    units = parse_content(candidate_text, source_name)
    plan_knowledge(units, candidate_text, source_name)
    cards = build_cards(units)
    errors = [
        violation
        for violation in validate_deck(cards, GenerationConfig(interleave_topics=False))
        if violation.level == "error"
    ]
    if errors:
        raise ValueError(f"generated Cornell candidate cards failed validation: {errors[0].code}")


def render_ai_cornell_note(
    source_text: str,
    source_name: str,
    *,
    course_slug: str,
    module_slug: str,
    title: str,
    tags: Sequence[str],
    provider: FileAiProvider | CommandAiProvider,
) -> str:
    validate_scalar(source_name, "source name")
    validate_scalar(course_slug, "course slug")
    validate_scalar(module_slug, "module slug")
    validate_scalar(title, "title")
    for tag in tags:
        validate_scalar(tag, "tag")
    units = parse_content(source_text, source_name)
    plan_knowledge(units, source_text, source_name)
    payload = parse_ai_payload(provider.complete(build_cornell_prompt(units)))
    note_tags = list(dict.fromkeys([*tags, course_slug, module_slug]))
    ai_cards = ai_candidate_cards(payload, units, note_tags)
    if not ai_cards:
        raise AiAuthoringError("AI Cornell response did not contain any candidate cards.")
    notes = evidence_backed_lines(payload.get("notes"), units, "notes")
    summary = evidence_backed_text(payload.get("summary"), units, "summary")
    gaps = coerce_text_lines(payload.get("follow_up_gaps", []), "follow_up_gaps")
    return render_note_document(
        source_name,
        course_slug=course_slug,
        module_slug=module_slug,
        title=title,
        note_tags=note_tags,
        cues=ai_cards,
        notes="\n\n".join(notes),
        summary=summary,
        gaps=gaps,
        cards=ai_cards,
    )


def render_note_document(
    source_name: str,
    *,
    course_slug: str,
    module_slug: str,
    title: str,
    note_tags: Sequence[str],
    cues: Sequence[tuple[str, str, str, list[str]]],
    notes: str,
    summary: str,
    gaps: Sequence[str],
    cards: Sequence[tuple[str, str, str, list[str]]],
) -> str:
    cue_rows = "\n".join(
        f"| {markdown_cell(front)} | {markdown_cell(back)} |"
        for front, back, _, _ in cues[:8]
    )
    card_blocks = "\n\n".join(
        "\n".join(
            [
                f"Q: {front}",
                f"A: {back}",
                f"Extra: {extra}",
                f"Tags: {' '.join(card_tags)}",
            ]
        )
        for front, back, extra, card_tags in cards
    )
    gap_lines = (
        "\n".join(f"- {gap}" for gap in gaps)
        or "- Review generated candidate cards against the source before import."
    )
    return (
        "---\n"
        f"courseSlug: {yaml_scalar(course_slug)}\n"
        f"moduleSlug: {yaml_scalar(module_slug)}\n"
        f"noteDate: {date.today().isoformat()}\n"
        "sourceFiles:\n"
        f"  - {yaml_scalar(source_name)}\n"
        "tags:\n"
        + "".join(f"  - {yaml_scalar(tag)}\n" for tag in note_tags)
        + "---\n\n"
        f"# {title} Cornell Notes\n\n"
        "## Source References\n\n"
        f"- `{source_name}`\n\n"
        "## Cues\n\n"
        "| Cue | Notes |\n"
        "| --- | --- |\n"
        f"{cue_rows}\n\n"
        "## Notes\n\n"
        f"{notes}\n\n"
        "## Summary\n\n"
        f"{summary}\n\n"
        "## Follow-Up Gaps\n\n"
        f"{gap_lines}\n\n"
        f"## {CANDIDATE_CARDS_SECTION}\n\n"
        f"{card_blocks}\n"
    )


def build_cornell_prompt(units: Sequence[SourceUnit]) -> str:
    return json.dumps(
        {
            "task": "Author a source-grounded Cornell note. Return JSON only.",
            "schema": {
                "notes": [
                    {
                        "text": "concise source-grounded note paragraph",
                        "source_unit_id": "id from source_units",
                        "evidence": "verbatim source span supporting the note",
                    }
                ],
                "summary": {
                    "text": "brief source-grounded summary",
                    "source_unit_id": "id from source_units",
                    "evidence": "verbatim source span supporting the summary",
                },
                "follow_up_gaps": ["uncertainties to review"],
                "candidate_cards": [
                    {
                        "source_unit_id": "id from source_units",
                        "question": "single concrete prompt",
                        "answer": "single source-grounded answer",
                        "extra": "Explanation: why this fact holds",
                        "tags": ["optional-tags"],
                        "evidence": "verbatim source span supporting the card",
                    }
                ],
            },
            "source_units": [
                {
                    "source_unit_id": unit.knowledge_unit_id,
                    "text": unit.text,
                    "question": unit.question,
                    "answer": unit.answer,
                    "extra": unit.extra,
                    "topic": unit.topic,
                    "source": unit.source,
                }
                for unit in units
            ],
        },
        ensure_ascii=False,
    )


def ai_candidate_cards(
    payload: dict[str, object],
    units: Sequence[SourceUnit],
    base_tags: Sequence[str],
) -> list[tuple[str, str, str, list[str]]]:
    drafts = payload.get("candidate_cards")
    if not isinstance(drafts, list):
        raise AiAuthoringError("AI Cornell response must contain a candidate_cards list.")
    units_by_id = {unit.knowledge_unit_id: unit for unit in units}
    cards: list[tuple[str, str, str, list[str]]] = []
    for draft in drafts:
        candidate = ai_candidate_card(draft, units_by_id, base_tags)
        if not candidate_is_valid(candidate):
            raise AiAuthoringError("AI Cornell candidate card failed validation.")
        cards.append(candidate)
    return cards


def ai_candidate_card(
    draft: object,
    units_by_id: dict[str, SourceUnit],
    base_tags: Sequence[str],
) -> tuple[str, str, str, list[str]]:
    if not isinstance(draft, dict):
        raise AiAuthoringError("AI Cornell candidate card must be an object.")
    required = ("source_unit_id", "question", "answer", "extra", "evidence")
    missing = [field for field in required if not str(draft.get(field, "")).strip()]
    if missing:
        raise AiAuthoringError(
            f"AI Cornell candidate is missing required fields: {', '.join(missing)}"
        )
    unit = units_by_id.get(str(draft["source_unit_id"]).strip())
    if unit is None:
        raise AiAuthoringError("AI Cornell candidate references unknown source_unit_id.")
    evidence = str(draft["evidence"]).strip()
    if not evidence_is_supported(evidence, unit):
        raise AiAuthoringError(
            "AI Cornell candidate evidence is not present in the referenced source unit."
        )
    question = plain_line(str(draft["question"]), "question")
    answer = plain_line(str(draft["answer"]), "answer")
    extra = plain_line(str(draft["extra"]), "extra")
    if not evidence_supports_answer(answer, evidence):
        raise AiAuthoringError("AI Cornell candidate answer is not supported by its evidence.")
    raw_tags = draft.get("tags", [])
    if not isinstance(raw_tags, list):
        raise AiAuthoringError("AI Cornell candidate tags must be a list.")
    draft_tags = [plain_line(str(tag), "tag") for tag in raw_tags if str(tag).strip()]
    tags = list(dict.fromkeys([*base_tags, *draft_tags, slugify(unit.topic)]))
    return (
        question,
        answer.rstrip("."),
        extra,
        tags,
    )


def evidence_backed_text(
    value: object,
    units: Sequence[SourceUnit],
    name: str,
) -> str:
    if not isinstance(value, dict):
        raise AiAuthoringError(f"AI Cornell response must contain {name}.")
    required = ("text", "source_unit_id", "evidence")
    missing = [field for field in required if not str(value.get(field, "")).strip()]
    if missing:
        raise AiAuthoringError(
            f"AI Cornell {name} is missing required fields: {', '.join(missing)}"
        )
    unit = {unit.knowledge_unit_id: unit for unit in units}.get(
        str(value["source_unit_id"]).strip()
    )
    if unit is None:
        raise AiAuthoringError(f"AI Cornell {name} references unknown source_unit_id.")
    evidence = str(value["evidence"]).strip()
    text = plain_markdown_paragraph(str(value["text"]), name)
    if not evidence_is_supported(evidence, unit):
        raise AiAuthoringError(
            f"AI Cornell {name} evidence is not present in the referenced source unit."
        )
    if normalize_evidence(text).rstrip(".") not in normalize_evidence(evidence):
        raise AiAuthoringError(f"AI Cornell {name} text is not supported by its evidence.")
    return text


def evidence_supports_answer(answer: str, evidence: str) -> bool:
    normalized_answer = normalize_evidence(answer).rstrip(".")
    normalized_evidence = normalize_evidence(evidence)
    if normalized_answer not in normalized_evidence:
        return False
    content_words = [
        word
        for word in re.findall(r"[A-Za-z0-9]+", normalized_answer)
        if len(word) > 2
    ]
    return len(content_words) >= 2


def coerce_text_lines(value: object, name: str) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [plain_line(value, name)]
    if isinstance(value, list):
        lines = [plain_line(str(item), name) for item in value if str(item).strip()]
        if lines:
            return lines
    raise AiAuthoringError(f"AI Cornell response must contain {name}.")


def evidence_backed_lines(
    value: object,
    units: Sequence[SourceUnit],
    name: str,
) -> list[str]:
    if not isinstance(value, list):
        raise AiAuthoringError(f"AI Cornell response must contain {name}.")
    lines = [evidence_backed_text(item, units, name) for item in value]
    if not lines:
        raise AiAuthoringError(f"AI Cornell response must contain {name}.")
    return lines


def plain_line(value: str, name: str) -> str:
    text = value.strip()
    if not text:
        raise AiAuthoringError(f"AI Cornell {name} must not be empty.")
    if any(character in text for character in "\r\n\t"):
        raise AiAuthoringError(f"AI Cornell {name} must be a single line.")
    return text


def plain_markdown_paragraph(value: str, name: str) -> str:
    text = value.strip()
    if not text:
        raise AiAuthoringError(f"AI Cornell {name} must not be empty.")
    if any(character in text for character in "\r\n\t"):
        raise AiAuthoringError(f"AI Cornell {name} must be a single paragraph.")
    if re.search(r"(^|\s)#{1,6}\s+", text):
        raise AiAuthoringError(f"AI Cornell {name} must not contain Markdown headings.")
    return text


def compact_notes(source_text: str) -> str:
    paragraphs = [
        line.strip()
        for line in source_text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return " ".join(paragraphs[:4]) or "Add concise source-grounded notes here."


def compact_summary(source_text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", compact_notes(source_text))
    return " ".join(sentence for sentence in sentences[:3] if sentence)


def build_ai_provider(args: argparse.Namespace) -> FileAiProvider | CommandAiProvider:
    providers = [bool(args.ai_response_file), bool(args.ai_command)]
    if args.author == "deterministic":
        if any(providers):
            raise AiAuthoringError("AI providers require --author ai.")
        raise AiAuthoringError("deterministic author does not use an AI provider.")
    if sum(providers) != 1:
        raise AiAuthoringError(
            "AI Cornell authoring requires exactly one of --ai-response-file or --ai-command."
        )
    return (
        FileAiProvider(args.ai_response_file)
        if args.ai_response_file
        else CommandAiProvider(args.ai_command)
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.source.exists():
        print(f"Source does not exist: {args.source}", file=sys.stderr)
        return 2
    try:
        if args.author != "ai" and (args.ai_response_file or args.ai_command):
            raise AiAuthoringError("AI providers require --author ai.")
        text = args.source.read_text(encoding="utf-8")
        if args.author == "ai":
            note = render_ai_cornell_note(
                text,
                args.source.name,
                course_slug=args.course_slug,
                module_slug=args.module_slug,
                title=args.title,
                tags=args.tag,
                provider=build_ai_provider(args),
            )
        else:
            note = render_cornell_note(
                text,
                args.source.name,
                course_slug=args.course_slug,
                module_slug=args.module_slug,
                title=args.title,
                tags=args.tag,
            )
        validate_contract(note, args.output.name)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(note, encoding="utf-8")
    except (OSError, UnicodeError, ValueError, AiAuthoringError) as exc:
        print(f"Cornell generation failed: {exc}", file=sys.stderr)
        return 2
    print(args.output)
    return 0
