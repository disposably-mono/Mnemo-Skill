""".apkg fallback backend: build an Anki package with genanki, offline.

Same role as connect.py, used when Anki desktop isn't running. Given
(Card, deck) pairs, this renders each Card via note_types.render_fields,
groups notes into decks, bundles fonts/media, and writes a single .apkg the
user imports by hand. Model/deck ids are derived deterministically from
their names so re-exporting the same deck updates the existing model/deck
on import instead of creating duplicates.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from mnemo.anki.fonts import bundled_font_paths, unique_media_paths
from mnemo.anki.note_types import NoteType, note_type_for, render_fields
from mnemo.card import Card

# genanki recommends model/deck ids in [1<<30, 1<<31); derived from the name
# so they're stable across runs (CRC32 is deterministic; offset into range).
_ID_BASE = 1 << 30
_ID_SPAN = 1 << 30


def _genanki():
    """Import genanki only when an offline package is being built."""
    import genanki

    return genanki


def stable_id(name: str) -> int:
    """A deterministic genanki id for a model/deck name, in the expected range."""
    return _ID_BASE + (zlib.crc32(name.encode("utf-8")) % _ID_SPAN)


@dataclass
class ExportResult:
    """Outcome of an export_apkg call."""

    path: Path
    count: int
    decks: list[str]


def _model_for(note_type: NoteType):
    genanki = _genanki()
    model_type = genanki.Model.CLOZE if note_type.is_cloze else genanki.Model.FRONT_BACK
    return genanki.Model(
        model_id=stable_id(note_type.name),
        name=note_type.name,
        fields=[{"name": f} for f in note_type.fields],
        templates=[
            {"name": t.name, "qfmt": t.qfmt, "afmt": t.afmt} for t in note_type.templates
        ],
        css=note_type.css,
        model_type=model_type,
    )


def _to_genanki_note(card: Card, note_type: NoteType):
    """Render a Card into a genanki Note, fields in note-type field order.

    A card with a stable CardID gets a guid derived from it, so re-exporting
    an edited card updates the existing Anki note on import instead of
    creating a duplicate (genanki's default guid is derived from all field
    values, so any edit would otherwise change it).
    """
    genanki = _genanki()
    model = _model_for(note_type)
    field_values = render_fields(card, note_type)
    fields = [field_values.get(name, "") for name in note_type.fields]
    guid = genanki.guid_for(note_type.name, card.card_id) if card.card_id else None
    return genanki.Note(model=model, fields=fields, tags=list(card.tags), guid=guid)


def export_apkg(cards: Iterable[tuple[Card, str]], path: str | Path) -> ExportResult:
    """Write (card, deck) pairs to a .apkg, one genanki Deck per distinct deck."""
    genanki = _genanki()
    path = Path(path)
    decks: dict[str, "genanki.Deck"] = {}
    count = 0
    for card, deck_name in cards:
        note_type = note_type_for(card.card_type)
        deck = decks.get(deck_name)
        if deck is None:
            deck = genanki.Deck(deck_id=stable_id(deck_name), name=deck_name)
            decks[deck_name] = deck
        deck.add_note(_to_genanki_note(card, note_type))
        count += 1

    media_files = unique_media_paths(bundled_font_paths())
    genanki.Package(
        list(decks.values()), media_files=[str(media) for media in media_files]
    ).write_to_file(str(path))
    return ExportResult(path=path, count=count, decks=list(decks))
