"""Data models and constants for flashcard generation."""

from __future__ import annotations

from dataclasses import dataclass, field

from .policy import (
    DEFAULT_EASE_PERCENT,
    DEFAULT_EASY_BUTTON_POLICY,
    DEFAULT_EASY_INTERVAL_DAYS,
    DEFAULT_GENERATION_SEED,
    DEFAULT_GRADUATING_INTERVAL_DAYS,
    DEFAULT_LEARNING_STEPS,
    DEFAULT_NEW_CARDS_PER_DAY,
    DEFAULT_SCHEDULER,
    MAX_COMPONENTS,
    MAX_FRONT_WORDS,
)

CSV_FIELDS = (
    "Front",
    "Back",
    "Extra",
    "Context",
    "Mnemonic",
    "CardType",
    "Tags",
    "ImageURL",
    "ImageAlt",
    "Topic",
    "Source",
    "CardID",
    "KnowledgeUnitID",
    "KnowledgeKind",
    "LearningPurpose",
    "ObjectiveIDs",
    "PrerequisiteIDs",
    "Origin",
    "Confidence",
)
CARD_TYPES = ("qa", "cloze", "reverse", "typed", "list", "image-supported")
DEFAULT_SEED = DEFAULT_GENERATION_SEED

@dataclass(frozen=True)
class GenerationConfig:
    learning_steps: tuple[str, ...] = DEFAULT_LEARNING_STEPS
    graduating_interval_days: int = DEFAULT_GRADUATING_INTERVAL_DAYS
    easy_interval_days: int = DEFAULT_EASY_INTERVAL_DAYS
    starting_ease_percent: int = DEFAULT_EASE_PERCENT
    max_ease_percent: int = DEFAULT_EASE_PERCENT
    new_cards_per_day: int = DEFAULT_NEW_CARDS_PER_DAY
    scheduler: str = DEFAULT_SCHEDULER
    easy_button_policy: str = DEFAULT_EASY_BUTTON_POLICY
    interleave_topics: bool = True
    seed: int = DEFAULT_SEED


@dataclass
class SourceUnit:
    text: str
    topic: str
    source: str
    question: str = ""
    answer: str = ""
    extra: str = ""
    tags: list[str] = field(default_factory=list)
    image_url: str = ""
    image_alt: str = ""
    group_components: list[str] = field(default_factory=list)
    knowledge_unit_id: str = ""
    knowledge_kind: str = "fact"
    learning_purpose: str = "recall"
    objective_ids: list[str] = field(default_factory=list)
    prerequisite_ids: list[str] = field(default_factory=list)
    origin: str = "source"
    confidence: float = 1.0
    verbatim_kind: str = ""
    verbatim_language: str = ""


@dataclass
class Card:
    front: str
    back: str
    extra: str
    context: str
    mnemonic: str
    card_type: str
    tags: list[str]
    topic: str
    source: str
    image_url: str = ""
    image_alt: str = ""
    card_id: str = ""
    knowledge_unit_id: str = ""
    knowledge_kind: str = "fact"
    learning_purpose: str = "recall"
    objective_ids: list[str] = field(default_factory=list)
    prerequisite_ids: list[str] = field(default_factory=list)
    origin: str = "source"
    confidence: float = 1.0

    def to_row(self) -> dict[str, str]:
        return {
            "Front": self.front,
            "Back": self.back,
            "Extra": self.extra,
            "Context": self.context,
            "Mnemonic": self.mnemonic,
            "CardType": self.card_type,
            "Tags": " ".join(dict.fromkeys(self.tags)),
            "ImageURL": self.image_url,
            "ImageAlt": self.image_alt,
            "Topic": self.topic,
            "Source": self.source,
            "CardID": self.card_id,
            "KnowledgeUnitID": self.knowledge_unit_id,
            "KnowledgeKind": self.knowledge_kind,
            "LearningPurpose": self.learning_purpose,
            "ObjectiveIDs": " ".join(self.objective_ids),
            "PrerequisiteIDs": " ".join(self.prerequisite_ids),
            "Origin": self.origin,
            "Confidence": f"{self.confidence:.4f}",
        }


@dataclass(frozen=True)
class Violation:
    level: str
    code: str
    message: str
    card_id: str = ""
    action: str = ""
