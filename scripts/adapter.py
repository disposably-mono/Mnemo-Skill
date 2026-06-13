"""Render a semantic Fact into a concrete Anki note (model + fields).

This is the interop layer. It targets the bundled MONO note types by default,
or stock/community note types through ``config.toml`` + ``mappings.toml``.

Distractors become an answer-side "common confusions" block (graded, never
interactive). Lists become an overlapping-cloze enumeration (one deletion per
item) — native and cross-platform, no add-on, no JavaScript.
"""

from __future__ import annotations

import html
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.card_schema import FACT_TYPES, Fact

# Default Fact-type -> MONO note type.
_DEFAULT_MODELS = {
    "qa": "MONO Basic",
    "cloze": "MONO Cloze",
    "list": "MONO Overlapping",
    "typed": "MONO Type",
    "image_occlusion": "Image Occlusion",
}

# Order matters: render the most plausible (near) confusions first.
_GRADE_ORDER = ("near", "medium", "far")
_PLACEHOLDER = re.compile(r"(?<!\{)\{([a-z_][a-z0-9_]*)\}(?!\})")


@dataclass
class AnkiNote:
    """A note ready for an import backend (AnkiConnect or genanki)."""

    model: str
    deck: str
    fields: dict[str, str]
    tags: list[str] = field(default_factory=list)
    media: list[Path] = field(default_factory=list)


Mappings = dict[str, dict[str, dict[str, str]]]


class MappingError(ValueError):
    """Raised when a configured target note type has no usable field mapping."""


def load_mappings(path: str | Path | None) -> Mappings:
    """Load mappings.toml (``{type: {model: {field: template}}}``) or return {}.

    A missing/None path means no external field mappings.
    """
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
    media_root: str | Path | None = None,
) -> AnkiNote:
    """Convert a validated Fact into an AnkiNote.

    With no mapping for ``fact.type`` it targets the bundled MONO note type.
    A mapping entry redirects the Fact to another note type, filling that type's
    fields from templates with ``{placeholder}`` tokens (see ``_placeholders``).
    """
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
        media: list[Path] = []
        image_name: str | None = None
        if fact.type == "image_occlusion":
            image_path = _resolve_image_path(fact, media_root)
            media = [image_path]
            image_name = image_path.name
        placeholders = _placeholders(fact, image_name=image_name)
        fields = {
            name: _fill(template, placeholders)
            for name, template in field_templates.items()
        }
        return AnkiNote(
            model=model_name,
            deck=fact.deck,
            fields=fields,
            tags=list(fact.tags),
            media=media,
        )

    fields, media = _BUILDERS[fact.type](fact, media_root)
    return AnkiNote(
        model=model_name,
        deck=fact.deck,
        fields=fields,
        tags=list(fact.tags),
        media=media,
    )


def _placeholders(
    fact: Fact, *, image_name: str | None = None
) -> dict[str, str]:
    """The substitution values available to a mapping template, by Fact type."""
    content = fact.content
    common = {
        "source": fact.source or "",
        "deck": fact.deck,
        "tags": " ".join(fact.tags),
    }
    if fact.type == "qa":
        return {**common, "front": content["front"], "back": content["back"],
                "distractors": _render_confusions(fact)}
    if fact.type == "cloze":
        return {**common, "text": content["text"], "extra": content.get("extra", ""),
                "distractors": _render_confusions(fact)}
    if fact.type == "list":
        return {**common, "title": content["title"], "items": _render_list_items(fact),
                "extra": content.get("extra", "")}
    if fact.type == "typed":
        return {
            **common,
            "prompt": content["prompt"],
            "answer": content["answer"],
            "hints": _render_hints(content.get("hints", [])),
            "extra": content.get("extra", ""),
        }
    return {
        **common,
        "image": (
            f'<img src="{html.escape(image_name, quote=True)}">'
            if image_name is not None
            else content["image"]
        ),
        "occlusion": _render_occlusions(content),
        "header": content.get("header", ""),
        "back_extra": content.get("back_extra", ""),
        "comments": content.get("comments", ""),
    }


def _fill(template: str, placeholders: dict[str, str]) -> str:
    """Replace known ``{key}`` tokens; literal braces elsewhere are left as-is."""
    unknown = set(_PLACEHOLDER.findall(template)) - set(placeholders)
    if unknown:
        joined = ", ".join(sorted(unknown))
        raise MappingError(f"unknown mapping placeholder(s): {joined}")
    out = template
    for key, value in placeholders.items():
        out = out.replace("{" + key + "}", value)
    return out


def _build_qa(
    fact: Fact, media_root: str | Path | None
) -> tuple[dict[str, str], list[Path]]:
    return ({
        "Front": fact.content["front"],
        "Back": fact.content["back"],
        "Distractors": _render_confusions(fact),
        "Source": fact.source or "",
    }, [])


def _build_cloze(
    fact: Fact, media_root: str | Path | None
) -> tuple[dict[str, str], list[Path]]:
    return ({
        "Text": fact.content["text"],
        "Extra": fact.content.get("extra", ""),
        "Distractors": _render_confusions(fact),
        "Source": fact.source or "",
    }, [])


def _build_list(
    fact: Fact, media_root: str | Path | None
) -> tuple[dict[str, str], list[Path]]:
    return ({
        "Title": fact.content["title"],
        "Text": _render_list_items(fact),
        "Source": fact.source or "",
    }, [])


def _build_typed(
    fact: Fact, media_root: str | Path | None
) -> tuple[dict[str, str], list[Path]]:
    content = fact.content
    hints = content.get("hints", [])
    return ({
        "Prompt": content["prompt"],
        "Answer": content["answer"],
        "Hint 1": hints[0] if len(hints) > 0 else "",
        "Hint 2": hints[1] if len(hints) > 1 else "",
        "Hint 3": hints[2] if len(hints) > 2 else "",
        "Extra": content.get("extra", ""),
        "Source": fact.source or "",
    }, [])


def _build_image_occlusion(
    fact: Fact, media_root: str | Path | None
) -> tuple[dict[str, str], list[Path]]:
    content = fact.content
    image_path = _resolve_image_path(fact, media_root)
    return ({
        "Occlusion": _render_occlusions(content),
        "Image": f'<img src="{html.escape(image_path.name, quote=True)}">',
        "Header": content.get("header", ""),
        "Back Extra": content.get("back_extra", ""),
        "Comments": content.get("comments", ""),
    }, [image_path])


def _resolve_image_path(fact: Fact, media_root: str | Path | None) -> Path:
    image_path = Path(fact.content["image"])
    if not image_path.is_absolute() and media_root is not None:
        image_path = Path(media_root) / image_path
    if not image_path.is_file():
        raise FileNotFoundError(f"image occlusion media not found: {image_path}")
    return image_path


def _render_list_items(fact: Fact) -> str:
    """An overlapping-cloze ``<ol>``: one numbered deletion per list item."""
    items = fact.content["items"]
    lis = "".join(
        f'<li>{{{{c{i}::{item}}}}}</li>' for i, item in enumerate(items, start=1)
    )
    return f'<ol class="mono-list">{lis}</ol>'


def _render_hints(hints: list[str]) -> str:
    return "<br>".join(hints)


def _render_occlusions(content: dict[str, Any]) -> str:
    suffix = ":oi=1" if content.get("occlude_inactive", True) else ""
    rendered: list[str] = []
    for index, mask in enumerate(content["masks"], start=1):
        ordinal = mask.get("card", index)
        shape = mask["shape"]
        if shape == "polygon":
            points = " ".join(f"{_number(x)},{_number(y)}" for x, y in mask["points"])
            properties = (
                f":left={_number(mask['left'])}:top={_number(mask['top'])}"
                f":points={points}"
            )
        else:
            keys = ("left", "top", "width", "height") if shape == "rect" else (
                "left", "top", "rx", "ry"
            )
            properties = "".join(f":{key}={_number(mask[key])}" for key in keys)
        rendered.append(
            f"{{{{c{ordinal}::image-occlusion:{shape}{properties}{suffix}}}}}<br>"
        )
    return "".join(rendered)


def _number(value: int | float) -> str:
    return format(value, ".6g")


def _render_confusions(fact: Fact) -> str:
    """Build the answer-side 'common confusions' HTML, grouped near->far."""
    if not fact.distractors:
        return ""
    items: list[str] = []
    for grade in _GRADE_ORDER:
        for d in fact.distractors:
            if d.grade == grade:
                items.append(f'<li class="{grade}">{d.text}</li>')
    body = "".join(items)
    return (
        '<div class="confusions">'
        '<div class="mono-label">Common confusions</div>'
        f"<ul>{body}</ul>"
        "</div>"
    )


_BUILDERS = {
    "qa": _build_qa,
    "cloze": _build_cloze,
    "list": _build_list,
    "typed": _build_typed,
    "image_occlusion": _build_image_occlusion,
}
