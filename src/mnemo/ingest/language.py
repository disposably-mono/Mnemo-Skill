"""Lightweight Filipino/English page-language classification.

Word-frequency heuristic over closed-class function words (articles,
pronouns, conjunctions, markers) -- the same "deterministic, no fabrication"
philosophy as the rest of the pipeline; no NLP model, no external service.
Good enough to separate predominantly-Filipino from predominantly-English
prose in bilingual documents (e.g. Philippine government FAQ booklets that
present each answer in both languages back to back). Can be fooled by a page
that quotes a long passage in the other language if the quote outweighs the
host page's own words -- callers filtering on this should treat "unknown"
as "keep" rather than silently dropping content they're not confident about.
"""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-zA-Zâàáäéèêëíìîïóòôöúùûüñ']+")
# Strip quoted spans before counting: a host-language page that quotes a
# short passage in the other language shouldn't have the quote's word
# frequency outweigh the page's own prose. Doesn't catch unquoted block
# excerpts (no delimiter to find) -- a real limit of a text-only heuristic.
_QUOTED_SPAN = re.compile(r"[\"“][^\"“”]*[\"”]")

# High-frequency, closed-class Filipino function words -- unlikely to appear
# as ordinary English words, so double-counting across languages is rare.
_FILIPINO_MARKERS = {
    "ang", "ng", "nang", "sa", "ay", "mga", "ito", "iyon", "iyan", "hindi",
    "na", "at", "para", "kung", "may", "wala", "kanilang", "niya", "nila",
    "siya", "kayâ", "kaya", "bagaman", "sapagkat", "dahil", "bansa", "wika",
    "bakit", "ano", "paano", "kaniyang", "ating", "atin", "mo", "ko", "ka",
    "tayo", "kami", "ito'y", "nga", "din", "rin", "lang", "lamang", "raw",
    "daw", "pa", "po", "opo", "yun", "yan", "sila", "ninyo", "natin",
}

# High-frequency, closed-class English function words.
_ENGLISH_MARKERS = {
    "the", "and", "of", "is", "are", "to", "in", "that", "for", "this",
    "was", "were", "with", "as", "it", "be", "by", "on", "from", "or",
    "an", "at", "not", "language", "national", "which", "there", "their",
    "have", "has", "had", "but", "its", "they", "we", "you", "he", "she",
    "his", "her", "will", "would", "can", "could", "should", "if", "so",
}


def classify_language(text: str) -> str:
    """Return "fil", "eng", or "unknown" for a chunk of text.

    "unknown" covers both "no signal at all" (e.g. a table of numbers) and
    a genuine tie -- callers must not treat "unknown" as "drop this".
    """
    text = _QUOTED_SPAN.sub(" ", text)
    words = _WORD.findall(text.lower())
    filipino = sum(1 for word in words if word in _FILIPINO_MARKERS)
    english = sum(1 for word in words if word in _ENGLISH_MARKERS)
    if filipino == english:
        return "unknown"
    return "fil" if filipino > english else "eng"
