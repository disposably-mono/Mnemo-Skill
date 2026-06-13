""".apkg fallback backend: build an Anki package with genanki.

Same role as ``anki_connect`` but offline — used when Anki desktop isn't running
to talk to. Given the adapter's ``AnkiNote``s, this renders the MONO note types
into genanki models, bundles their fonts/media, groups notes into decks, and
writes a single ``.apkg`` the user imports by hand (File -> Import in Anki).

Model and deck ids are derived deterministically from their names so that
re-exporting the same deck updates the existing model/deck on import instead of
creating duplicates.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import genanki

from scripts.adapter import AnkiNote
from scripts.media import bundled_font_paths, unique_media_paths
from scripts.note_types import MONO_NOTE_TYPES, NoteType

# genanki recommends model/deck ids in [1<<30, 1<<31). We derive them from the
# name so they're stable across runs (CRC32 is deterministic; offset into range).
_ID_BASE = 1 << 30
_ID_SPAN = 1 << 30


def stable_id(name: str) -> int:
    """A deterministic genanki id for a model/deck name, in the expected range."""
    return _ID_BASE + (zlib.crc32(name.encode("utf-8")) % _ID_SPAN)


@dataclass
class ExportResult:
    """Outcome of an export_apkg call."""

    path: Path
    count: int
    decks: list[str]


def model_for(note_type: NoteType) -> genanki.Model:
    """Build a genanki Model mirroring a MONO NoteType (cloze flag preserved)."""
    model_type = genanki.Model.CLOZE if note_type.is_cloze else genanki.Model.FRONT_BACK
    return genanki.Model(
        model_id=stable_id(note_type.name),
        name=note_type.name,
        fields=[{"name": f} for f in note_type.fields],
        templates=[
            {"name": t.name, "qfmt": t.qfmt, "afmt": t.afmt}
            for t in note_type.templates
        ],
        css=note_type.css,
        model_type=model_type,
    )


def to_genanki_note(note: AnkiNote, note_type: NoteType) -> genanki.Note:
    """Render an AnkiNote into a genanki Note with fields in note-type order."""
    model = model_for(note_type)
    fields = [note.fields.get(name, "") for name in note_type.fields]
    return genanki.Note(model=model, fields=fields, tags=list(note.tags))


def export_apkg(
    notes: Iterable[AnkiNote],
    path: str | Path,
    note_types: dict[str, NoteType] = MONO_NOTE_TYPES,
) -> ExportResult:
    """Write notes to a .apkg, one genanki Deck per distinct deck name."""
    path = Path(path)
    notes = list(notes)
    decks: dict[str, genanki.Deck] = {}
    count = 0
    for note in notes:
        note_type = note_types[note.model]  # KeyError on unknown model (by design)
        deck = decks.get(note.deck)
        if deck is None:
            deck = genanki.Deck(deck_id=stable_id(note.deck), name=note.deck)
            decks[note.deck] = deck
        deck.add_note(to_genanki_note(note, note_type))
        count += 1

    note_media = [media for note in notes for media in note.media]
    media_files = unique_media_paths([*bundled_font_paths(), *note_media])
    genanki.Package(
        list(decks.values()), media_files=[str(media) for media in media_files]
    ).write_to_file(str(path))
    return ExportResult(path=path, count=count, decks=list(decks))
