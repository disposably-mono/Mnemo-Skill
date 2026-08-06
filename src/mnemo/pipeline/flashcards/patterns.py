"""Regular expressions used by flashcard generation."""

from __future__ import annotations

import re

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
_OBJECTIVE_HEADER = re.compile(r"^(?:learning\s+)?objectives?\s*:\s*$", re.IGNORECASE)
_BULLET = re.compile(r"^\s*(?:[-*+] |\d+[.)]\s+)(.+)$")
_CLOZE = re.compile(r"\{\{c\d+::(.*?)(?:::[^}]*)?\}\}")
_WORDS = re.compile(r"(?:[^\W\d_]|\d)+(?:[-'](?:[^\W\d_]|\d)+)*")
_FACT_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
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
# Case-sensitive: only genuine all-caps runs (e.g. "DNA", "API") count as
# acronyms. Folding this under IGNORECASE would match any 2+ letter word.
_ACRONYM = re.compile(r"\b[A-Z]{2,}\b")
_TECHNICAL_KEYWORDS = re.compile(
    r"\b(?:theorem|algorithm|enzyme|protocol|doctrine|statute|"
    r"coefficient|derivative|mitosis|syntax|jurisdiction)\b",
    re.IGNORECASE,
)
