"""Text normalization and splitting helpers for flashcard generation."""

from __future__ import annotations

import re

from mnemo.core.verbatim import (
    protect_inline_verbatim,
    restore_inline_verbatim,
    without_inline_verbatim,
)

from .patterns import (
    _CLOZE,
    _DEFINE,
    _FACT_BOUNDARY,
    _VERB,
    _WHAT_IS,
    _WHAT_MEANS,
    _WORDS,
)

def word_count(text: str) -> int:
    return len(_WORDS.findall(strip_html_and_cloze(text)))


def strip_html_and_cloze(text: str) -> str:
    text = without_inline_verbatim(text)
    text = _CLOZE.sub(lambda match: match.group(1), text)
    return re.sub(r"<[^>]+>", " ", text)


def has_cloze(text: str) -> bool:
    """Return whether text contains cloze markup outside inline verbatim spans."""
    return bool(_CLOZE.search(without_inline_verbatim(text)))


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "general"



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
    protected, spans = protect_inline_verbatim(text)
    parts: list[str] = []
    start = 0
    for boundary in _FACT_BOUNDARY.finditer(protected):
        preceding = protected[:boundary.start()].rstrip()
        token = re.search(r"(\S+)[.!?]+$", preceding)
        last = token.group(1).lower() if token else ""
        # Skip splitting after known abbreviations or single-letter initials.
        if last in _ABBREVIATIONS or re.fullmatch(r"[a-z]", last):
            continue
        segment = restore_inline_verbatim(protected[start:boundary.start()].strip(), spans)
        if segment:
            parts.append(segment)
        start = boundary.end()
    tail = restore_inline_verbatim(protected[start:].strip(), spans)
    if tail:
        parts.append(tail)
    return parts



_THOUSANDS_COMMA = re.compile(r"(?<=\d),(?=\d{3}\b)")


def protect_thousands_commas(text: str) -> str:
    return _THOUSANDS_COMMA.sub("\x00", text)


def split_list_items(text: str) -> list[str]:
    if not text or not re.search(r"[,;]", text):
        return []
    protected, spans = protect_inline_verbatim(protect_thousands_commas(text))
    if ";" in protected:
        items = [part.strip(" .") for part in protected.split(";") if part.strip(" .")]
    else:
        normalized = re.sub(r",?\s+(?:and|or)\s+", ", ", protected, flags=re.IGNORECASE)
        items = [part.strip(" .") for part in normalized.split(",") if part.strip(" .")]
    items = [restore_inline_verbatim(item.replace("\x00", ","), spans) for item in items]
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
    protected, spans = protect_inline_verbatim(text)
    if re.search(
        r"\b(?:but|whereas|while|however|therefore|because|evidence|claim|exception)\b",
        protected,
        re.IGNORECASE,
    ):
        return [text.strip()]
    semicolon_parts = [part.strip(" .") for part in protected.split(";") if part.strip(" .")]
    if len(semicolon_parts) > 1 and all(_VERB.search(part) for part in semicolon_parts):
        return [restore_inline_verbatim(part + ".", spans) for part in semicolon_parts]
    parts = re.split(r"\s+and\s+", protected, flags=re.IGNORECASE)
    if len(parts) == 2 and all(word_count(part) >= 3 and _VERB.search(part) for part in parts):
        return [restore_inline_verbatim(part.strip(" .") + ".", spans) for part in parts]
    return [text.strip()]

def definition_term(question: str) -> str:
    for pattern in (_WHAT_IS, _DEFINE, _WHAT_MEANS):
        match = pattern.match(question.strip())
        if match:
            term = match.group("term").strip(" .?")
            if re.match(r"^(?:answer\s+)?component\b", term, re.IGNORECASE):
                return ""
            return term
    return ""
