"""Shared policy constants for flashcard generation."""

from __future__ import annotations

CANDIDATE_CARDS_SECTION = "Candidate Cards"

MAX_FRONT_WORDS = 19
MAX_COMPONENTS = 4
MAX_LIST_ITEMS = 8
MAX_LIST_ITEM_WORDS = 12
DEFAULT_GENERATION_SEED = 42

DEFAULT_LEARNING_STEPS = ("10m", "1d")
DEFAULT_LEARNING_STEP_DELAYS_MINUTES = (10.0, 1440.0)
DEFAULT_GRADUATING_INTERVAL_DAYS = 3
DEFAULT_EASY_INTERVAL_DAYS = 7
DEFAULT_EASE_PERCENT = 250
DEFAULT_NEW_CARDS_PER_DAY = 20
DEFAULT_SCHEDULER = "legacy-sm2"
DEFAULT_EASY_BUTTON_POLICY = "avoid"
DEFAULT_AI_COMMAND_TIMEOUT_S = 120

GENERIC_PROMPT_STEMS = (
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

SEQUENCE_PREFIX_CUES = (
    "shift",
    "move",
    "progress",
    "proceed",
    "transition",
    "sequence",
    "hierarchy",
    "scale",
    "pathway",
    "continuum",
)

CLAUSE_MARKER_VERBS = ("was", "were", "appeared", "placed", "challenged")

SEMANTIC_STOPWORDS = frozenset(
    {
        "and", "the", "this", "that", "with", "from", "into", "what", "when",
        "where", "which", "able", "students", "learners", "explain", "identify",
        "understand", "describe", "apply",
    }
)

SENTENCE_ABBREVIATIONS = frozenset(
    {
        "e.g", "i.e", "etc", "vs", "al", "cf", "approx", "no", "fig", "eq",
        "dr", "mr", "mrs", "ms", "prof", "st", "mt", "u.s", "u.k", "ph.d",
        "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct",
        "nov", "dec",
    }
)

TECHNICAL_KEYWORDS = (
    "theorem",
    "algorithm",
    "enzyme",
    "protocol",
    "doctrine",
    "statute",
    "coefficient",
    "derivative",
    "mitosis",
    "syntax",
    "jurisdiction",
)
