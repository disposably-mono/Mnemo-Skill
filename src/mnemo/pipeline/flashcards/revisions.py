"""Shared canonical rendered-card payload helpers for revision hashing."""

from __future__ import annotations

import html
from typing import Mapping, Sequence

from mnemo.core.identity import revision_hash as compute_revision_hash


def rendered_card_payload(
    *,
    front: str,
    back: str,
    extra: str,
    context: str,
    mnemonic: str,
    card_type: str,
    tags: Sequence[str],
    topic: str,
    source: str,
    image_url: str,
    image_alt: str,
    knowledge_unit_id: str,
    knowledge_kind: str,
    learning_purpose: str,
    objective_ids: Sequence[str],
    prerequisite_ids: Sequence[str],
    origin: str,
    confidence: float | int | str | None,
) -> dict[str, object]:
    normalized_image_url = image_url
    normalized_image_alt = image_alt
    return {
        "front": front,
        "back": _normalize_back(back, normalized_image_url, normalized_image_alt),
        "extra": extra,
        "context": context,
        "mnemonic": mnemonic,
        "card_type": card_type,
        "tags": list(dict.fromkeys(tags)),
        "topic": topic,
        "source": source,
        "image_url": normalized_image_url,
        "image_alt": normalized_image_alt,
        "knowledge_unit_id": knowledge_unit_id,
        "knowledge_kind": knowledge_kind,
        "learning_purpose": learning_purpose,
        "objective_ids": list(objective_ids),
        "prerequisite_ids": list(prerequisite_ids),
        "origin": origin,
        "confidence": _normalize_confidence(confidence),
    }


def rendered_card_revision_hash(**kwargs: object) -> str:
    return compute_revision_hash(rendered_card_payload(**kwargs))


def rendered_card_payload_from_row(row: Mapping[str, str]) -> dict[str, object]:
    return rendered_card_payload(
        front=_row_text(row, "Front"),
        back=_row_text(row, "Back"),
        extra=_row_text(row, "Extra"),
        context=_row_text(row, "Context"),
        mnemonic=_row_text(row, "Mnemonic"),
        card_type=(row.get("CardType") or "").strip(),
        tags=(row.get("Tags") or "").split(),
        topic=_row_text(row, "Topic"),
        source=_row_text(row, "Source"),
        image_url=_row_text(row, "ImageURL"),
        image_alt=_row_text(row, "ImageAlt"),
        knowledge_unit_id=(row.get("KnowledgeUnitID") or "").strip(),
        knowledge_kind=(row.get("KnowledgeKind") or "").strip(),
        learning_purpose=(row.get("LearningPurpose") or "recall").strip(),
        objective_ids=(row.get("ObjectiveIDs") or "").split(),
        prerequisite_ids=(row.get("PrerequisiteIDs") or "").split(),
        origin=(row.get("Origin") or "").strip(),
        confidence=(row.get("Confidence") or "").strip() or None,
    )


def rendered_card_revision_hash_from_row(row: Mapping[str, str]) -> str:
    return compute_revision_hash(rendered_card_payload_from_row(row))


def _row_text(row: Mapping[str, str], key: str) -> str:
    return html.unescape((row.get(key) or "").strip())


def _normalize_confidence(value: float | int | str | None) -> float | str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value.strip())
    except ValueError:
        return value.strip()


def _normalize_back(back: str, image_url: str, image_alt: str) -> str:
    if not image_url:
        return back
    raw_suffix = f'<br><img src="{image_url}" alt="{image_alt}">'
    escaped_suffix = (
        f'<br><img src="{html.escape(image_url, quote=True)}" '
        f'alt="{html.escape(image_alt, quote=True)}">'
    )
    for suffix in (raw_suffix, escaped_suffix):
        if back.endswith(suffix):
            return back[: -len(suffix)]
    return back
