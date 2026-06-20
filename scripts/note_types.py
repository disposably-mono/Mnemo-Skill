"""MONO reference note types: the styled, MIT-licensed default targets.

These are the note types the adapter renders Facts into by default. They are
plain data here (name, fields, card templates, CSS) so they can be validated
without Anki or genanki installed; the import backends turn them into real
models (AnkiConnect ``createModel`` / genanki ``Model``).

Design system: built from the MONO color and typography tokens. Per Anki
convention the default ``.card`` is the *light* theme and ``.nightMode`` carries
the *dark* theme (Anki toggles ``.nightMode``, not ``[data-theme]``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Anki template tokens that are not note fields.
_BUILTIN_TOKENS = {"FrontSide", "Tags", "Type", "Deck", "Subdeck", "Card", "CardFlag"}
_FIELD_REF = re.compile(r"\{\{([^{}]+)\}\}")


def referenced_fields(template_text: str) -> set[str]:
    """Return the note-field names a card template references.

    Strips section markers (``#`` / ``^`` / ``/``) and filters (``cloze:`` /
    ``type:``), and ignores Anki's built-in tokens like ``{{FrontSide}}``.
    """
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
    qfmt: str  # question (front) format
    afmt: str  # answer (back) format


@dataclass(frozen=True)
class NoteType:
    name: str
    fields: tuple[str, ...]
    templates: tuple[CardTemplate, ...]
    css: str
    is_cloze: bool = False


# --------------------------------------------------------------------------
# Shared styling — the MONO design-system port.
# --------------------------------------------------------------------------

MONO_CSS = """\
/* MONO note-type styling. */
@font-face {
  font-family: 'DM Serif Display';
  src: url('_dmserifdisplay-regular.ttf');
  font-weight: 400;
}
@font-face {
  font-family: 'DM Mono';
  src: url('_dmmono-regular.ttf');
  font-weight: 400;
}
@font-face {
  font-family: 'DM Mono';
  src: url('_dmmono-medium.ttf');
  font-weight: 500;
}
@font-face {
  font-family: 'Outfit';
  src: url('_outfit-variable.ttf');
  font-weight: 100 900;
}

.card {
  --bg: #EAF0CE;            /* beige ground (light) */
  --bg-2: #dfe6bb;
  --text-primary: #34312D;  /* graphite */
  --text-sec: #5F5E5A;
  --text-muted: #8D99AE;
  --accent: #3B6D11;        /* fern-dark (light-theme accent) */
  --highlight: #534AB7;     /* plum */
  --border: rgba(52, 49, 45, 0.10);
  --font-serif: 'DM Serif Display', Georgia, serif;
  --font-sans: 'Outfit', system-ui, sans-serif;
  --font-mono: 'DM Mono', ui-monospace, SFMono-Regular, monospace;
  --radius-md: 12px;
  --hair: 0.5px;

  font-family: var(--font-sans);
  font-weight: 300;
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
  --bg: #34312D;            /* graphite ground (dark) */
  --bg-2: #3d3a35;
  --text-primary: #EAF0CE;  /* beige */
  --text-sec: #8D99AE;      /* lavender-grey */
  --text-muted: #5F5E5A;
  --accent: #588157;        /* fern */
  --highlight: #E5D4ED;     /* lavender */
  --border: rgba(234, 240, 206, 0.08);
}

.mono-label {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 10px;
}

.mono-q {
  font-family: var(--font-serif);
  font-size: 30px;
  line-height: 1.15;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}

.mono-a { margin-top: 4px; }

.cloze { font-weight: 500; color: var(--accent); }

hr#answer {
  border: none;
  border-top: var(--hair) solid var(--border);
  margin: 22px 0;
}

ol.mono-list { padding-left: 1.4em; }
ol.mono-list li { margin: 6px 0; }

/* Answer-side "common confusions" — graded distractors, never interactive. */
.confusions {
  margin-top: 22px;
  padding: 14px 16px;
  border: var(--hair) solid var(--border);
  border-radius: var(--radius-md);
  font-size: 15px;
}
.confusions .mono-label { color: var(--text-muted); }
.confusions ul { list-style: none; margin: 0; padding: 0; }
.confusions li { padding: 3px 0; color: var(--text-sec); }
.confusions .near { color: var(--highlight); }

.source {
  margin-top: 18px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.12em;
  color: var(--text-muted);
}

.mono-hints { margin-top: 18px; }
.mono-hints a {
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.08em;
}

#typeans { font-family: var(--font-mono); }
"""


# --------------------------------------------------------------------------
# Bundled MONO note types.
# --------------------------------------------------------------------------

_DISTRACTORS_BLOCK = "{{#Distractors}}{{Distractors}}{{/Distractors}}"
_SOURCE_BLOCK = '{{#Source}}<div class="source">{{Source}}</div>{{/Source}}'

MONO_BASIC = NoteType(
    name="MONO Basic",
    fields=("Front", "Back", "Distractors", "Source"),
    templates=(
        CardTemplate(
            name="Card 1",
            qfmt='<div class="mono-label">Recall</div><div class="mono-q">{{Front}}</div>',
            afmt=(
                "{{FrontSide}}"
                '<hr id="answer">'
                '<div class="mono-a">{{Back}}</div>'
                + _DISTRACTORS_BLOCK
                + _SOURCE_BLOCK
            ),
        ),
    ),
    css=MONO_CSS,
    is_cloze=False,
)

MONO_CLOZE = NoteType(
    name="MONO Cloze",
    fields=("Text", "Extra", "Distractors", "Source"),
    templates=(
        CardTemplate(
            name="Cloze",
            qfmt='<div class="mono-label">Fill in</div><div class="mono-a">{{cloze:Text}}</div>',
            afmt=(
                '<div class="mono-label">Fill in</div>'
                '<div class="mono-a">{{cloze:Text}}</div>'
                "{{#Extra}}<div class=\"mono-a\">{{Extra}}</div>{{/Extra}}"
                + _DISTRACTORS_BLOCK
                + _SOURCE_BLOCK
            ),
        ),
    ),
    css=MONO_CSS,
    is_cloze=True,
)

# Lists/enumerations: a cloze model whose Text is an enumerated cloze list
# (each item its own deletion). Native + cross-platform; no add-on, no JS.
MONO_OVERLAPPING = NoteType(
    name="MONO Overlapping",
    fields=("Title", "Text", "Source"),
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
    fields=("Prompt", "Answer", "Hint 1", "Hint 2", "Hint 3", "Extra", "Source"),
    templates=(
        CardTemplate(
            name="Typed Answer",
            qfmt=(
                '<div class="mono-label">Type the answer</div>'
                '<div class="mono-q">{{Prompt}}</div>'
                '<div class="mono-hints">'
                '{{#Hint 1}}{{hint:Hint 1}}{{/Hint 1}}'
                '{{#Hint 2}}<br>{{hint:Hint 2}}{{/Hint 2}}'
                '{{#Hint 3}}<br>{{hint:Hint 3}}{{/Hint 3}}'
                '</div>{{type:Answer}}'
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
