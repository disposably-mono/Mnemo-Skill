"""Data models and constants for flashcard generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

CSV_FIELDS = (
    "Front",
    "Back",
    "Extra",
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
MAX_FRONT_WORDS = 19  # Rubric says fewer than 20 words.
MAX_COMPONENTS = 4
DEFAULT_SEED = 42

@dataclass(frozen=True)
class GenerationConfig:
    learning_steps: tuple[str, ...] = ("10m", "1d")
    graduating_interval_days: int = 3
    easy_interval_days: int = 7
    starting_ease_percent: int = 250
    max_ease_percent: int = 250
    new_cards_per_day: int = 20
    scheduler: str = "legacy-sm2"
    easy_button_policy: str = "avoid"
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
