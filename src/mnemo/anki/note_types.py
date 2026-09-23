"""MONO reference note types: the styled, MIT-licensed default targets.

Plain data (name, fields, card templates, CSS) so they can be validated
without Anki or genanki installed; the import backends turn them into real
models (AnkiConnect ``createModel`` / genanki ``Model``). Ported from the
pre-rewrite package -- MONO Code (verbatim rendering, unused by the current
card-type scope) and Image Occlusion (cut per the architecture plan) are
dropped; every field list here includes ``RevisionHash`` from the start,
fixing the old "missing field on a fresh Anki profile" bug at the source
instead of patching it post-import.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_BUILTIN_TOKENS = {"FrontSide", "Tags", "Type", "Deck", "Subdeck", "Card", "CardFlag"}
_FIELD_REF = re.compile(r"\{\{([^{}]+)\}\}")


def referenced_fields(template_text: str) -> set[str]:
    """Return the note-field names a card template references."""
    refs: set[str] = set()
    for match in _FIELD_REF.finditer(template_text):
        token = match.group(1).strip().lstrip("#^/").strip()
        if ":" in token:
            token = token.split(":")[-1].strip()
        if token and token not in _BUILTIN_TOKENS:
            refs.add(token)
    return refs


@dataclass(frozen=True)
class CardTemplate:
    name: str
    qfmt: str
    afmt: str


@dataclass(frozen=True)
class NoteType:
    name: str
    fields: tuple[str, ...]
    templates: tuple[CardTemplate, ...]
    css: str
    is_cloze: bool = False


MONO_CSS = """\
.card {
  --bg: #EAF0CE;
  --text-primary: #34312D;
  --text-sec: #5F5E5A;
  --text-muted: #8D99AE;
  --accent: #3B6D11;
  --highlight: #534AB7;
  --border: rgba(52, 49, 45, 0.10);
  font-family: system-ui, sans-serif;
  font-size: 19px;
  line-height: 1.7;
  color: var(--text-primary);
  background: var(--bg);
  max-width: 680px;
  margin: 0 auto;
  padding: 28px 24px;
  text-align: left;
}
.card.nightMode, .nightMode .card {
  --bg: #34312D;
  --text-primary: #EAF0CE;
  --text-sec: #8D99AE;
  --text-muted: #5F5E5A;
  --accent: #588157;
  --highlight: #E5D4ED;
  --border: rgba(234, 240, 206, 0.08);
}
.mono-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 10px;
}
.mono-q { font-size: 30px; line-height: 1.15; color: var(--text-primary); }
.mono-a { margin-top: 4px; }
.cloze { font-weight: 500; color: var(--accent); }
hr#answer { border: none; border-top: 0.5px solid var(--border); margin: 22px 0; }
.source { margin-top: 18px; font-size: 10px; letter-spacing: 0.12em; color: var(--text-muted); }
.mono-hints { margin-top: 18px; }
"""

_SOURCE_BLOCK = '{{#Source}}<div class="source">{{Source}}</div>{{/Source}}'

MONO_BASIC = NoteType(
    name="MONO Basic",
    fields=("Front", "Back", "Source", "CardID", "RevisionHash"),
    templates=(
        CardTemplate(
            name="Card 1",
            qfmt='<div class="mono-label">Recall</div><div class="mono-q">{{Front}}</div>',
            afmt=(
                "{{FrontSide}}"
                '<hr id="answer">'
                '<div class="mono-a">{{Back}}</div>'
                + _SOURCE_BLOCK
            ),
        ),
    ),
    css=MONO_CSS,
    is_cloze=False,
)

MONO_CLOZE = NoteType(
    name="MONO Cloze",
    fields=("Text", "Extra", "Source", "CardID", "RevisionHash"),
    templates=(
        CardTemplate(
            name="Cloze",
            qfmt='<div class="mono-label">Fill in</div><div class="mono-a">{{cloze:Text}}</div>',
            afmt=(
                '<div class="mono-label">Fill in</div>'
                '<div class="mono-a">{{cloze:Text}}</div>'
                '{{#Extra}}<div class="mono-a">{{Extra}}</div>{{/Extra}}'
                + _SOURCE_BLOCK
            ),
        ),
    ),
    css=MONO_CSS,
    is_cloze=True,
)

MONO_OVERLAPPING = NoteType(
    name="MONO Overlapping",
    fields=("Title", "Text", "Source", "CardID", "RevisionHash"),
    templates=(
        CardTemplate(
            name="Overlapping",
            qfmt='<div class="mono-label">{{Title}}</div><div class="mono-a">{{cloze:Text}}</div>',
            afmt=(
                '<div class="mono-label">{{Title}}</div>'
                '<div class="mono-a">{{cloze:Text}}</div>'
                + _SOURCE_BLOCK
            ),
        ),
    ),
    css=MONO_CSS,
    is_cloze=True,
)

MONO_TYPE = NoteType(
    name="MONO Type",
    fields=("Prompt", "Answer", "Extra", "Source", "CardID", "RevisionHash"),
    templates=(
        CardTemplate(
            name="Typed Answer",
            qfmt=(
                '<div class="mono-label">Type the answer</div>'
                '<div class="mono-q">{{Prompt}}</div>{{type:Answer}}'
            ),
            afmt=(
                '<div class="mono-label">Type the answer</div>'
                '<div class="mono-q">{{Prompt}}</div>'
                '<hr id="answer">{{type:Answer}}'
                '<div class="mono-a">{{Answer}}</div>'
                '{{#Extra}}<div class="mono-a">{{Extra}}</div>{{/Extra}}'
                + _SOURCE_BLOCK
            ),
        ),
    ),
    css=MONO_CSS,
)

MONO_NOTE_TYPES: dict[str, NoteType] = {
    nt.name: nt for nt in (MONO_BASIC, MONO_CLOZE, MONO_OVERLAPPING, MONO_TYPE)
}
