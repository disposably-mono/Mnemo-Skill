"""Import orchestrator + CLI: the last mile of the pipeline.

Loads approved Facts from a JSONL file (the review-gate output), adapts each into
a note for the target MONO type, then imports them — live via AnkiConnect when
Anki desktop is reachable, otherwise by writing a ``.apkg`` the user imports by
hand. This is the script ``SKILL.md`` step 5 runs:

    python scripts/import_cards.py cards/<session>.jsonl [--sync]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Allow running directly as a script (`python scripts/import_cards.py ...`, the
# form SKILL.md documents) by putting the repo root on the path before importing
# the `scripts` package.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.adapter import AnkiNote, adapt
from scripts.anki_connect import AnkiConnect
from scripts.card_schema import load_facts
from scripts.genanki_export import export_apkg
from scripts.note_types import MONO_NOTE_TYPES, NoteType


@dataclass
class ImportReport:
    """What happened during an import, for a user-facing summary."""

    backend: str            # "ankiconnect" | "apkg"
    added: int = 0
    skipped: int = 0
    synced: bool = False
    apkg_path: Path | None = None
    decks: list[str] = field(default_factory=list)


def _adapt_all(jsonl_path: Path) -> list[AnkiNote]:
    return [adapt(fact) for fact in load_facts(jsonl_path)]


def _used_note_types(
    notes: list[AnkiNote], note_types: dict[str, NoteType]
) -> list[NoteType]:
    """The NoteType objects referenced by these notes, deduped, order-stable."""
    seen: dict[str, NoteType] = {}
    for note in notes:
        if note.model in note_types and note.model not in seen:
            seen[note.model] = note_types[note.model]
    return list(seen.values())


def import_cards(
    jsonl_path: str | Path,
    *,
    client: AnkiConnect | None = None,
    sync: bool = False,
    apkg_out: str | Path | None = None,
    note_types: dict[str, NoteType] = MONO_NOTE_TYPES,
) -> ImportReport:
    """Import approved Facts, preferring AnkiConnect with a .apkg fallback."""
    jsonl_path = Path(jsonl_path)
    notes = _adapt_all(jsonl_path)
    decks = list(dict.fromkeys(n.deck for n in notes))  # distinct, order-stable

    if client is None:
        client = AnkiConnect()

    if client.is_available():
        client.ensure_note_types(_used_note_types(notes, note_types))
        for deck in decks:
            client.ensure_deck(deck)
        result = client.add_notes(notes)
        report = ImportReport(
            backend="ankiconnect",
            added=len(result.added),
            skipped=result.skipped,
            decks=decks,
        )
        if sync:
            client.sync()
            report.synced = True
        return report

    # Fallback: Anki isn't running — write a package to import manually.
    out = Path(apkg_out) if apkg_out else jsonl_path.with_suffix(".apkg")
    export = export_apkg(notes, out, note_types=note_types)
    return ImportReport(
        backend="apkg",
        added=export.count,
        apkg_path=export.path,
        decks=export.decks,
    )


def _format_summary(report: ImportReport) -> str:
    if report.backend == "ankiconnect":
        line = f"Imported via AnkiConnect: {report.added} added, {report.skipped} skipped."
        if report.synced:
            line += " AnkiWeb sync triggered."
        return line
    return (
        f"Anki not reachable — wrote {report.added} cards to {report.apkg_path}. "
        "Import it with File -> Import in Anki."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import approved Facts into Anki.")
    parser.add_argument("jsonl", help="Path to the approved cards/<session>.jsonl")
    parser.add_argument("--sync", action="store_true",
                        help="Trigger an AnkiWeb sync after a live import.")
    parser.add_argument("--url", default=None,
                        help="AnkiConnect URL (default: http://localhost:8765).")
    parser.add_argument("--apkg-out", default=None,
                        help="Override the .apkg fallback path.")
    args = parser.parse_args(argv)

    client = AnkiConnect(args.url) if args.url else None
    report = import_cards(
        args.jsonl, client=client, sync=args.sync, apkg_out=args.apkg_out
    )
    print(_format_summary(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
