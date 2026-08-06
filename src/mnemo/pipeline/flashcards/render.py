"""Render source units into concrete flashcards."""

from __future__ import annotations

import hashlib
import html
import random
import re
from collections import Counter, defaultdict, deque
from typing import Sequence

from mnemo.core.verbatim import has_inline_verbatim, without_inline_verbatim

from .models import DEFAULT_SEED, Card, SourceUnit
from .patterns import (
    _ACRONYM,
    _CLOZE,
    _DEFINITION,
    _RELATION,
    _TECHNICAL_KEYWORDS,
    _VERB,
)
from .text import (
    definition_term,
    enumerated_components,
    has_cloze,
    semantic_tokens,
    slugify,
    strip_html_and_cloze,
    word_count,
)

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
        verbatim_tag = ["mnemo-verbatim-code"] if unit.verbatim_kind == "code" else []
        tags = [*unit.tags, *verbatim_tag, slugify(unit.topic), "auto"]
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
    if (
        unit.verbatim_kind
        or has_inline_verbatim(unit.text)
        or has_inline_verbatim(unit.answer)
        or re.search(r"\\[A-Za-z]+", f"{unit.text} {unit.answer}")
    ):
        return "qa"
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
    if unit.verbatim_kind == "math":
        return "What expression is displayed?", unit.text
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
    if has_cloze(statement):
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
    answers = _CLOZE.findall(without_inline_verbatim(cloze))
    return "; ".join(answers) if answers else cloze



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
    return bool(
        _ACRONYM.search(text)
        or _TECHNICAL_KEYWORDS.search(text)
        or re.search(r"\b[A-Za-z]+\d+\b", text)
    )


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
