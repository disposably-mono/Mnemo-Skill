"""Rubric validation for generated flashcards."""

from __future__ import annotations

import re
from collections import Counter
from typing import Sequence

from mnemo.core.knowledge import KNOWLEDGE_KINDS, LEARNING_PURPOSES, ORIGINS

from .models import CARD_TYPES, MAX_COMPONENTS, MAX_FRONT_WORDS, Card, GenerationConfig, Violation
from .patterns import _VERB
from .render import (
    MAX_LIST_ITEMS,
    authored_list_components,
    explanation_is_thin,
    first_alnum,
    is_generic_prompt,
    requires_context,
)
from .policy import (
    DEFAULT_EASE_PERCENT,
    DEFAULT_EASY_BUTTON_POLICY,
    DEFAULT_EASY_INTERVAL_DAYS,
    DEFAULT_GRADUATING_INTERVAL_DAYS,
    DEFAULT_NEW_CARDS_PER_DAY,
)
from .text import (
    enumerated_components,
    has_cloze,
    protect_thousands_commas,
    strip_html_and_cloze,
    word_count,
)

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
    if not card.extra.strip():
        violations.append(error("MISSING_EXPLANATION", "Extra must contain an explanation.", card, "Add pre-understanding context in Extra."))
    if requires_context(card.front, card.back) and not card.context.strip():
        violations.append(error("MISSING_CONTEXT", "Technical card lacks a Context section.", card, "Add the prerequisite domain context."))
    if card.card_type not in CARD_TYPES:
        violations.append(error("INVALID_CARD_TYPE", f"Unknown card type {card.card_type!r}.", card, f"Use one of: {', '.join(CARD_TYPES)}."))
    if card.card_type == "cloze" and not has_cloze(card.front):
        violations.append(error("CLOZE_FORMAT", "Cloze card does not contain Anki cloze syntax.", card, "Add one {{c1::answer}} deletion or change CardType."))
    if card.card_type != "cloze" and has_cloze(card.front):
        violations.append(error("TYPE_FORMAT_MISMATCH", f"{card.card_type} card contains cloze syntax.", card, "Render a direct prompt or set CardType to cloze."))
    if card.card_type == "reverse" and not card.front.startswith("Which term means:"):
        violations.append(error("REVERSE_FORMAT", "Reverse card is not a term-from-definition prompt.", card, "Render 'Which term means: <definition>?' or change CardType."))
    if card.card_type == "list":
        violations.extend(validate_list_contract(card))
    component_count = estimate_components(card.back)
    if card.card_type != "list" and component_count > MAX_COMPONENTS:
        violations.append(error("COGNITIVE_LOAD", f"Back appears to contain {component_count} components.", card, "Split into atomic cards with at most four components."))
    if card.card_type != "list" and looks_compound(card.back):
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


def validate_list_contract(card: Card) -> list[Violation]:
    violations: list[Violation] = []
    components = authored_list_components(strip_html_and_cloze(card.back))
    if not 3 <= len(components) <= MAX_LIST_ITEMS:
        violations.append(error("LIST_SIZE", "List cards require 3 to 8 bounded components.", card, "Split or rewrite the list card."))
        return violations
    expected = "".join(first_alnum(component).upper() for component in components)
    actual = card.mnemonic.split(":", 1)[0].strip().upper()
    if actual != expected:
        violations.append(error("MNEMONIC_MISMATCH", "List mnemonic does not match component initials.", card, f"Use mnemonic prefix {expected}."))
    return violations


def estimate_components(text: str) -> int:
    clean = protect_thousands_commas(strip_html_and_cloze(text))
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
    if config.new_cards_per_day > DEFAULT_NEW_CARDS_PER_DAY:
        violations.append(Violation("error", "DAILY_LIMIT", f"New cards/day is {config.new_cards_per_day}; maximum is {DEFAULT_NEW_CARDS_PER_DAY}.", action=f"Set --new-cards-per-day to {DEFAULT_NEW_CARDS_PER_DAY} or fewer."))
    if config.graduating_interval_days != DEFAULT_GRADUATING_INTERVAL_DAYS:
        violations.append(Violation("warning", "GRADUATING_INTERVAL", f"Graduating interval differs from the requested {DEFAULT_GRADUATING_INTERVAL_DAYS}-day baseline.", action=f"Use --graduating-interval {DEFAULT_GRADUATING_INTERVAL_DAYS} unless intentionally overridden."))
    if config.easy_interval_days != DEFAULT_EASY_INTERVAL_DAYS:
        violations.append(Violation("warning", "EASY_INTERVAL", f"Easy interval differs from the requested {DEFAULT_EASY_INTERVAL_DAYS}-day baseline.", action=f"Use --easy-interval {DEFAULT_EASY_INTERVAL_DAYS} unless intentionally overridden."))
    if config.max_ease_percent > DEFAULT_EASE_PERCENT:
        violations.append(Violation("error", "EASE_CAP", f"Maximum ease exceeds {DEFAULT_EASE_PERCENT}%.", action=f"Set --max-ease to {DEFAULT_EASE_PERCENT} or lower."))
    if config.starting_ease_percent > config.max_ease_percent:
        violations.append(Violation("error", "STARTING_EASE", "Starting ease exceeds the configured ease cap.", action="Set starting ease at or below max ease."))
    if config.easy_button_policy != DEFAULT_EASY_BUTTON_POLICY:
        violations.append(Violation("error", "EASY_POLICY", f"Easy-button policy must remain {DEFAULT_EASY_BUTTON_POLICY!r} for this rubric.", action=f"Set easy_button_policy to {DEFAULT_EASY_BUTTON_POLICY}."))
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
