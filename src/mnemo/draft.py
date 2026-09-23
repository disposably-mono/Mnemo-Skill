"""The deterministic drafter: source Chunks -> grounded Cards + deferred units.

Per SKILL.md, the drafter only emits a card when it can ground it confidently:
explicit Q&A, single-line `::` or tab pairs, colon-delimited definitions, and
a bulleted enumeration under a clear stem line. Anything it can't ground with
one of these patterns is left as a DeferredUnit for the agent to author --
never a fabricated prompt. There is no KnowledgeUnit/objective classification
here (that layer was cut); grounding is purely pattern-based.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from mnemo.card import Card, CardValidationError
from mnemo.ingest import Chunk

_HEADING = re.compile(r"^#{1,6}\s+(.+)$")
_TOPIC_LINE = re.compile(r"^Topic:\s*(.+)$", re.IGNORECASE)
# Lettered section headers ("A. Wikang Panturo") are common in textbook-style
# prose (notably Philippine educational material) but aren't Markdown
# headings. Require no trailing sentence punctuation and a short line so an
# abbreviated name ("A. Reyes ang pangalan...") isn't mistaken for one.
_LETTERED_SECTION = re.compile(r"^([A-Z])\.\s+(.+)$")
_MAX_SECTION_HEADER_WORDS = 15
_Q_LINE = re.compile(r"^Q:\s*(.+)$")
_A_LINE = re.compile(r"^A:\s*(.+)$")
_EXTRA_LINE = re.compile(r"^Extra:\s*(.+)$")
_MNEMONIC_LINE = re.compile(r"^Mnemonic:\s*(.+)$")
_TAGS_LINE = re.compile(r"^Tags:\s*(.+)$")
_DOUBLE_COLON = re.compile(r"^(.+?)\s*::\s*(.+)$")
_BULLET = re.compile(r"^[-*]\s+(.+)$")
# No digits in the term: excludes "Figure 3:", "Table 1:" caption-style labels.
_DEFINITION_LINE = re.compile(r"^([A-Za-z][A-Za-z \-']{1,60}):\s*(.+)$")
_MAX_DEFINITION_TERM_WORDS = 4
# Caption/cross-reference keywords that are not definitions even when they fit
# the "Term: text" shape (e.g. "Figure: ...", "Note: ...", "See: ...").
_NON_DEFINITION_TERMS = {
    "figure", "fig", "table", "tbl", "note", "notes", "warning", "caution",
    "see", "example", "exhibit", "chart", "diagram", "image", "source",
}
# A stem line plus at least two bullets is the minimum bar for "confident"
# list grounding (a single-item list isn't a meaningful enumeration).
_MIN_STEM_BULLET_LINES = 3


@dataclass
class DeferredUnit:
    """A source excerpt the drafter couldn't confidently ground into a card."""

    text: str
    source: str
    reason: str


def draft_cards(
    chunks: list[Chunk], *, deck: str = ""
) -> tuple[list[Card], list[DeferredUnit]]:
    """Draft cards from ingested Chunks, deferring anything not confidently grounded."""
    cards: list[Card] = []
    deferred: list[DeferredUnit] = []
    for chunk in chunks:
        topic: str | None = None
        for block in _split_blocks(chunk.text):
            heading_topic = _extract_topic(block)
            if heading_topic is not None:
                topic = heading_topic
                continue
            # A grounder can match a pattern but still fail Card's own
            # validation (e.g. front too long) -- that must defer the block,
            # not crash the whole draft run and lose every other card in it.
            try:
                card = _ground_block(block, topic=topic, source=chunk.source)
            except CardValidationError as exc:
                card = None
                reason = f"matched a grounding pattern but failed validation: {exc}"
            else:
                reason = "no confident grounding pattern matched"
            if card is not None:
                cards.append(card)
            else:
                deferred.append(
                    DeferredUnit(
                        text=block,
                        source=chunk.source,
                        reason=reason,
                    )
                )
    return cards, deferred


def _split_blocks(text: str) -> list[str]:
    normalized = _isolate_section_headers(text.strip())
    return [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]


def _isolate_section_headers(text: str) -> str:
    """Force a lettered section header to start its own block even when the
    source has no blank line before it (common in copy-pasted textbook
    prose, e.g. Philippine educational material's "A./B./C." subsections)."""
    lines = text.split("\n")
    out_lines: list[str] = []
    for index, line in enumerate(lines):
        if index > 0 and out_lines and out_lines[-1].strip() and _section_header_title(line):
            out_lines.append("")
        out_lines.append(line)
    return "\n".join(out_lines)


def _section_header_title(line: str) -> str | None:
    match = _LETTERED_SECTION.match(line.strip())
    if match is None:
        return None
    title = match.group(2).strip()
    if title.endswith((".", "!", "?")) or len(title.split()) > _MAX_SECTION_HEADER_WORDS:
        return None
    return title


def _extract_topic(block: str) -> str | None:
    """A block that is only a heading/Topic:/lettered-section line sets the
    running topic."""
    lines = block.splitlines()
    if len(lines) != 1:
        return None
    section_title = _section_header_title(lines[0])
    if section_title is not None:
        return section_title
    match = _HEADING.match(lines[0]) or _TOPIC_LINE.match(lines[0])
    return match.group(1).strip() if match else None


def _ground_block(block: str, *, topic: str | None, source: str) -> Card | None:
    for grounder in (_ground_qa_block, _ground_double_colon, _ground_tab_pair,
                      _ground_stem_bullets, _ground_definition_line):
        card = grounder(block, topic=topic, source=source)
        if card is not None:
            return card
    return None


def _ground_qa_block(block: str, *, topic: str | None, source: str) -> Card | None:
    lines = block.splitlines()
    q_match = next((m for line in lines if (m := _Q_LINE.match(line))), None)
    a_match = next((m for line in lines if (m := _A_LINE.match(line))), None)
    if q_match is None or a_match is None:
        return None
    extra_match = next((m for line in lines if (m := _EXTRA_LINE.match(line))), None)
    mnemonic_match = next((m for line in lines if (m := _MNEMONIC_LINE.match(line))), None)
    tags_match = next((m for line in lines if (m := _TAGS_LINE.match(line))), None)
    return Card(
        front=q_match.group(1).strip(),
        back=a_match.group(1).strip(),
        extra=extra_match.group(1).strip() if extra_match else "",
        mnemonic=mnemonic_match.group(1).strip() if mnemonic_match else "",
        card_type="qa",
        tags=tags_match.group(1).split() if tags_match else [],
        topic=topic,
        source=source,
    )


def _ground_double_colon(block: str, *, topic: str | None, source: str) -> Card | None:
    if "\n" in block:
        return None
    match = _DOUBLE_COLON.match(block)
    if match is None:
        return None
    return Card(
        front=match.group(1).strip(),
        back=match.group(2).strip(),
        card_type="qa",
        topic=topic,
        source=source,
    )


def _ground_tab_pair(block: str, *, topic: str | None, source: str) -> Card | None:
    if "\n" in block or "\t" not in block:
        return None
    parts = [p.strip() for p in block.split("\t")]
    if len(parts) != 2 or not all(parts):
        return None
    return Card(front=parts[0], back=parts[1], card_type="qa", topic=topic, source=source)


def _ground_definition_line(block: str, *, topic: str | None, source: str) -> Card | None:
    if "\n" in block:
        return None
    match = _DEFINITION_LINE.match(block)
    if match is None:
        return None
    term = match.group(1).strip()
    definition = match.group(2).strip()
    if not term or not definition:
        return None
    if not _looks_like_a_definable_term(term):
        return None
    return Card(
        front=f"What is {_lower_first(term)}?",
        back=_capitalize_first(definition),
        card_type="qa",
        topic=topic,
        source=source,
    )


def _looks_like_a_definable_term(term: str) -> bool:
    """Reject caption/cross-reference labels that only look like definitions.

    "Figure 3: ...", "Note: ...", "See: ..." fit the same "Term: text" shape
    as a real definition, but are not one -- grounding them fabricates a
    nonsensical card, which the drafter must never do (defer instead).
    """
    words = term.split()
    if len(words) > _MAX_DEFINITION_TERM_WORDS:
        return False
    if words[0].lower() in _NON_DEFINITION_TERMS:
        return False
    return True


def _ground_stem_bullets(block: str, *, topic: str | None, source: str) -> Card | None:
    lines = block.splitlines()
    if len(lines) < _MIN_STEM_BULLET_LINES or not lines[0].rstrip().endswith(":"):
        return None
    bullet_matches = [_BULLET.match(line) for line in lines[1:]]
    if not bullet_matches or any(m is None for m in bullet_matches):
        return None
    stem = lines[0].rstrip()[:-1].strip()
    if not stem:
        return None
    items = [m.group(1).strip() for m in bullet_matches]
    return Card(
        front=f"{stem}?",
        back="; ".join(items),
        card_type="list",
        topic=topic,
        source=source,
    )


def write_deferred(path: str | Path, units: list[DeferredUnit]) -> None:
    """Write deferred units as a plain, agent-readable Markdown file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not units:
        path.write_text("No deferred units -- every block was confidently grounded.\n")
        return
    lines = ["# Deferred units", "", "The drafter could not confidently ground these",
             "source excerpts into a card. Author them directly, or leave them", "deferred with a reason.", ""]
    for unit in units:
        lines.append(f"## {_escape_heading_text(unit.source)}")
        lines.append(f"Reason: {unit.reason}")
        lines.append("")
        lines.append(_fence(unit.text))
        lines.append("")
    path.write_text("\n".join(lines))


def _escape_heading_text(text: str) -> str:
    """Strip leading Markdown heading markers so source names can't be
    mistaken for a different heading level when rendered."""
    return text.lstrip("#").strip() or text


def _fence(text: str) -> str:
    """Wrap text in a code fence long enough to not be broken out of by any
    backtick run already inside it (source content, not document structure)."""
    longest_run = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest_run + 1)
    return f"{fence}\n{text}\n{fence}"


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text else text


def _capitalize_first(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text
