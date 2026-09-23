"""The audit rubric: validate drafted/authored Cards before import.

Per SKILL.md: errors block import, warnings require conscious review against
the source. Heuristics can flag likely compounds and thin explanations but
cannot prove semantic atomicity -- judge each case. Unlike the old audit,
this operates directly on mnemo.card.Card (already contract-validated at
construction) with no KnowledgeUnit/coverage-sidecar dependency.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from mnemo.card import Card

_CLOZE_OPEN = re.compile(r"\{\{")
_CLOZE_CLOSE = re.compile(r"\}\}")
_CLOZE_PAIR = re.compile(r"\{\{([^{}]*)\}\}")
_CLOZE_DELETION = re.compile(r"^c\d+::(.*)$")
# A front this short is unlikely to be independently gradable; below this,
# flag for human review rather than silently trusting it (SKILL.md rule 1).
_MIN_GENERIC_PROMPT_WORDS = 3
# Heuristic only: also false-positives on domain terms containing "and"/"or"
# as a whole word (e.g. "the AND gate", "the OR operator") -- acceptable
# since this is a review-me warning, never a blocking error.
_COMPOUND_MARKERS = (" and ", " or ", "; ")


@dataclass
class Violation:
    """One audit finding against a single card (or the deck as a whole)."""

    level: str  # "error" | "warning"
    code: str
    message: str
    card_id: str | None = None


@dataclass
class AuditReport:
    """The audit's overall verdict and summary for a deck of cards."""

    status: str  # "PASS" | "FAIL"
    violations: list[Violation]
    card_count: int
    card_types: dict[str, int]

    @property
    def errors(self) -> int:
        return sum(1 for v in self.violations if v.level == "error")

    @property
    def warnings(self) -> int:
        return sum(1 for v in self.violations if v.level == "warning")


def audit_cards(cards: list[Card]) -> list[Violation]:
    """Run every rubric check and return the combined violation list."""
    violations: list[Violation] = []
    violations.extend(_duplicate_violations(cards))
    for card in cards:
        violations.extend(_check_card(card))
    return violations


def build_report(cards: list[Card]) -> AuditReport:
    """Audit a deck and summarize the result as a PASS/FAIL report."""
    violations = audit_cards(cards)
    errors = sum(1 for v in violations if v.level == "error")
    return AuditReport(
        status="FAIL" if errors else "PASS",
        violations=violations,
        card_count=len(cards),
        card_types=dict(Counter(card.card_type for card in cards)),
    )


def _check_card(card: Card) -> list[Violation]:
    checks = [
        _cloze_syntax_violation,
        _thin_explanation_violation,
        _generic_prompt_violation,
        _atomicity_violation,
        _missing_source_violation,
    ]
    violations = [v for check in checks if (v := check(card)) is not None]
    return violations


def _duplicate_violations(cards: list[Card]) -> list[Violation]:
    """Flag every card in a duplicate Front/Back group, not just the first."""
    signatures = Counter((c.front.strip().casefold(), c.back.strip().casefold()) for c in cards)
    violations = []
    for card in cards:
        sig = (card.front.strip().casefold(), card.back.strip().casefold())
        if signatures[sig] > 1:
            violations.append(
                Violation(
                    "warning",
                    "DUPLICATE_CARD",
                    f"The same Front/Back pair appears {signatures[sig]} times.",
                    card_id=card.card_id,
                )
            )
    return violations


def _cloze_syntax_violation(card: Card) -> Violation | None:
    """Every {{...}} pair must be a valid, non-empty {{c#::...}} deletion.

    Counting open/close braces alone lets a real deletion mask a malformed
    sibling pair (e.g. "{{c1::x}} {{stray}}" is brace-balanced but "stray"
    isn't valid cloze markup and Anki would render it as literal text).
    """
    if card.card_type != "cloze":
        return None
    opens = len(_CLOZE_OPEN.findall(card.front))
    closes = len(_CLOZE_CLOSE.findall(card.front))
    pairs = _CLOZE_PAIR.findall(card.front)
    if opens != closes or not pairs:
        return Violation(
            "error", "CLOZE_SYNTAX",
            "Cloze card has no balanced {{c#::...}} deletion.", card_id=card.card_id,
        )
    for inner in pairs:
        match = _CLOZE_DELETION.match(inner)
        if match is None:
            return Violation(
                "error", "CLOZE_SYNTAX",
                f"Cloze card contains malformed cloze markup: {{{{{inner}}}}}.",
                card_id=card.card_id,
            )
        if not match.group(1).strip():
            return Violation(
                "error", "CLOZE_SYNTAX",
                "Cloze card has an empty deletion.", card_id=card.card_id,
            )
    return None


def _thin_explanation_violation(card: Card) -> Violation | None:
    if card.extra.strip():
        return None
    return Violation(
        "warning", "THIN_EXPLANATION",
        "Extra is empty; add an Explanation: of why the fact holds.",
        card_id=card.card_id,
    )


def _generic_prompt_violation(card: Card) -> Violation | None:
    if len(card.front.split()) >= _MIN_GENERIC_PROMPT_WORDS:
        return None
    return Violation(
        "warning", "GENERIC_PROMPT",
        "Front is very short; check it is specific enough to grade independently.",
        card_id=card.card_id,
    )


def _atomicity_violation(card: Card) -> Violation | None:
    lowered = f" {card.front.lower()} "
    if not any(marker in lowered for marker in _COMPOUND_MARKERS):
        return None
    return Violation(
        "warning", "ATOMICITY_REVIEW",
        "Front may test more than one fact; consider splitting into separate cards.",
        card_id=card.card_id,
    )


def _missing_source_violation(card: Card) -> Violation | None:
    if card.source:
        return None
    return Violation(
        "warning", "MISSING_SOURCE",
        "Card has no source provenance recorded.", card_id=card.card_id,
    )
