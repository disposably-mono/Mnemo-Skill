"""Render a semantic Fact into a concrete Anki note (model + fields).

This is the interop seam. For v1 it targets the bundled MONO note types; the
field-mapping layer for stock/community note types (driven by ``mappings.toml``)
plugs in here in Phase 2 without changing the Fact contract or the generator.

Distractors become an answer-side "common confusions" block (graded, never
interactive). Lists become an overlapping-cloze enumeration (one deletion per
item) — native and cross-platform, no add-on, no JavaScript.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from scripts.card_schema import Fact

# Default Fact-type -> MONO note type.
_DEFAULT_MODELS = {
    "qa": "MONO Basic",
    "cloze": "MONO Cloze",
    "list": "MONO Overlapping",
}

# Order matters: render the most plausible (near) confusions first.
_GRADE_ORDER = ("near", "medium", "far")


@dataclass
class AnkiNote:
    """A note ready for an import backend (AnkiConnect or genanki)."""

    model: str
    deck: str
    fields: dict[str, str]
    tags: list[str] = field(default_factory=list)


def adapt(fact: Fact) -> AnkiNote:
    """Convert a validated Fact into an AnkiNote targeting a MONO note type."""
    model = _DEFAULT_MODELS[fact.type]
    builder = _BUILDERS[fact.type]
    fields = builder(fact)
    return AnkiNote(model=model, deck=fact.deck, fields=fields, tags=list(fact.tags))


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
    items = fact.content["items"]
    lis = "".join(
        f'<li>{{{{c{i}::{item}}}}}</li>' for i, item in enumerate(items, start=1)
    )
    return {
        "Title": fact.content["title"],
        "Text": f'<ol class="mono-list">{lis}</ol>',
        "Source": fact.source or "",
    }


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
}
