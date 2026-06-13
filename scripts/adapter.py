"""Render a semantic Fact into a concrete Anki note (model + fields).

The bundled MONO models are the defaults. ``config.toml`` can select a stock
or community model, while ``mappings.toml`` describes how Fact values populate
that model's fields.

Distractors become an answer-side "common confusions" block (graded, never
interactive). Lists become an overlapping-cloze enumeration (one deletion per
item) -- native and cross-platform, no add-on or JavaScript.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from scripts.card_schema import FACT_TYPES, Fact

_DEFAULT_MODELS = {
    "qa": "MONO Basic",
    "cloze": "MONO Cloze",
    "list": "MONO Overlapping",
}

_GRADE_ORDER = ("near", "medium", "far")
_PLACEHOLDER = re.compile(r"(?<!\{)\{([a-z_][a-z0-9_]*)\}(?!\})")


@dataclass
class AnkiNote:
    """A note ready for an import backend (AnkiConnect or genanki)."""

    model: str
    deck: str
    fields: dict[str, str]
    tags: list[str] = field(default_factory=list)


Mappings = dict[str, dict[str, dict[str, str]]]


class MappingError(ValueError):
    """Raised when a configured target note type has no usable field mapping."""


def load_mappings(path: str | Path | None) -> Mappings:
    """Load field mappings from TOML, or return an empty mapping if absent."""
    if path is None:
        return {}
    path = Path(path)
    if not path.exists():
        return {}
    with path.open("rb") as fh:
        mappings = tomllib.load(fh)
    _validate_mappings(mappings)
    return mappings


def _validate_mappings(mappings: object) -> None:
    if not isinstance(mappings, dict):
        raise MappingError("mappings.toml must contain tables")
    for fact_type, models in mappings.items():
        if fact_type not in FACT_TYPES:
            raise MappingError(f"unknown mapped fact type: {fact_type!r}")
        if not isinstance(models, dict) or not models:
            raise MappingError(f"mapping for {fact_type!r} must contain a model table")
        for model, fields in models.items():
            if not isinstance(model, str) or not model.strip():
                raise MappingError(f"mapping for {fact_type!r} has an invalid model name")
            if not isinstance(fields, dict) or not fields:
                raise MappingError(f"mapping for model {model!r} must define fields")
            if not all(
                isinstance(name, str) and isinstance(template, str)
                for name, template in fields.items()
            ):
                raise MappingError(f"mapping fields for {model!r} must be strings")


def adapt(
    fact: Fact,
    mappings: Mappings | None = None,
    target_models: dict[str, str] | None = None,
) -> AnkiNote:
    """Convert a validated Fact into fields for its configured Anki model."""
    configured_target = (target_models or {}).get(fact.type)
    mapping_group = (mappings or {}).get(fact.type, {})
    if configured_target is None and mapping_group:
        configured_target = next(iter(mapping_group))
    model_name = configured_target or _DEFAULT_MODELS[fact.type]

    if model_name != _DEFAULT_MODELS[fact.type]:
        field_templates = mapping_group.get(model_name)
        if field_templates is None:
            raise MappingError(
                f"no [{fact.type}.{model_name!r}] field mapping found"
            )
        placeholders = _placeholders(fact)
        fields = {
            name: _fill(template, placeholders)
            for name, template in field_templates.items()
        }
    else:
        fields = _BUILDERS[fact.type](fact)

    return AnkiNote(
        model=model_name,
        deck=fact.deck,
        fields=fields,
        tags=list(fact.tags),
    )


def _placeholders(fact: Fact) -> dict[str, str]:
    common = {
        "source": fact.source or "",
        "deck": fact.deck,
        "tags": " ".join(fact.tags),
    }
    content = fact.content
    if fact.type == "qa":
        return {
            **common,
            "front": content["front"],
            "back": content["back"],
            "distractors": _render_confusions(fact),
        }
    if fact.type == "cloze":
        return {
            **common,
            "text": content["text"],
            "extra": content.get("extra", ""),
            "distractors": _render_confusions(fact),
        }
    return {
        **common,
        "title": content["title"],
        "items": _render_list_items(fact),
        "extra": content.get("extra", ""),
    }


def _fill(template: str, placeholders: dict[str, str]) -> str:
    unknown = set(_PLACEHOLDER.findall(template)) - set(placeholders)
    if unknown:
        joined = ", ".join(sorted(unknown))
        raise MappingError(f"unknown mapping placeholder(s): {joined}")
    out = template
    for key, value in placeholders.items():
        out = out.replace("{" + key + "}", value)
    return out


def _build_qa(fact: Fact) -> dict[str, str]:
    return {
        "Front": fact.content["front"],
        "Back": fact.content["back"],
        "Distractors": _render_confusions(fact),
        "Source": fact.source or "",
    }


def _build_cloze(fact: Fact) -> dict[str, str]:
    return {
        "Text": fact.content["text"],
        "Extra": fact.content.get("extra", ""),
        "Distractors": _render_confusions(fact),
        "Source": fact.source or "",
    }


def _build_list(fact: Fact) -> dict[str, str]:
    return {
        "Title": fact.content["title"],
        "Text": _render_list_items(fact),
        "Source": fact.source or "",
    }


def _render_list_items(fact: Fact) -> str:
    items = fact.content["items"]
    lis = "".join(
        f'<li>{{{{c{i}::{item}}}}}</li>' for i, item in enumerate(items, start=1)
    )
    return f'<ol class="mono-list">{lis}</ol>'


def _render_confusions(fact: Fact) -> str:
    if not fact.distractors:
        return ""
    items: list[str] = []
    for grade in _GRADE_ORDER:
        for distractor in fact.distractors:
            if distractor.grade == grade:
                items.append(f'<li class="{grade}">{distractor.text}</li>')
    return (
        '<div class="confusions">'
        '<div class="mono-label">Common confusions</div>'
        f"<ul>{''.join(items)}</ul>"
        "</div>"
    )


_BUILDERS = {
    "qa": _build_qa,
    "cloze": _build_cloze,
    "list": _build_list,
}
