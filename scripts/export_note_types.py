"""Export the bundled MONO note types as an installable ``.apkg``.

Reusing the genanki backend, this writes a tiny package containing the MONO
models (templates + styling) with one example note each. A user imports it once
via File -> Import in Anki to get the styled note types, then Mnemo's live
AnkiConnect imports target them. Run:

    python scripts/export_note_types.py -o mnemo-note-types.apkg
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # allow `python scripts/export_note_types.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.adapter import AnkiNote
from scripts.genanki_export import ExportResult, export_apkg
from scripts.note_types import MONO_NOTE_TYPES, NoteType

DEFAULT_OUT = "mnemo-note-types.apkg"
INSTALL_DECK = "Mnemo Note Types"

# One illustrative note per MONO type so the import shows the styling in action.
_EXAMPLES: dict[str, dict[str, str]] = {
    "MONO Basic": {
        "Front": "What kind of cards does Mnemo author?",
        "Back": "Atomic, recall-first cards.",
        "Distractors": "",
        "Source": "Mnemo example",
    },
    "MONO Cloze": {
        "Text": "Mnemo keeps every card {{c1::atomic}} — one idea each.",
        "Extra": "",
        "Distractors": "",
        "Source": "Mnemo example",
    },
    "MONO Overlapping": {
        "Title": "The Mnemo pipeline",
        "Text": (
            '<ol class="mono-list">'
            "<li>{{c1::ingest}}</li><li>{{c2::generate}}</li>"
            "<li>{{c3::review}}</li><li>{{c4::import}}</li>"
            "</ol>"
        ),
        "Source": "Mnemo example",
    },
}


def export_note_types(
    path: str | Path,
    note_types: dict[str, NoteType] = MONO_NOTE_TYPES,
    deck: str = INSTALL_DECK,
) -> ExportResult:
    """Write a .apkg with each known note type's example note in one deck."""
    notes = [
        AnkiNote(model=name, deck=deck, fields=fields, tags=["mnemo", "example"])
        for name, fields in _EXAMPLES.items()
        if name in note_types
    ]
    return export_apkg(notes, path, note_types=note_types)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Export the MONO note types as an installable .apkg."
    )
    parser.add_argument("-o", "--out", default=DEFAULT_OUT,
                        help=f"Output path (default: {DEFAULT_OUT}).")
    args = parser.parse_args(argv)

    result = export_note_types(args.out)
    print(f"Wrote {result.count} note-type examples to {result.path}. "
          "Import it in Anki with File -> Import.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
