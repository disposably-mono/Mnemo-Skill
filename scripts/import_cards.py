"""Import orchestrator + CLI: the last mile of the pipeline.

Loads approved Facts from a JSONL file (the review-gate output), adapts each into
a note for its configured target type, then imports them — live via AnkiConnect
when Anki desktop is reachable, otherwise by writing a ``.apkg`` the user
imports by hand. This is the script ``SKILL.md`` step 5 runs:

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

from scripts.adapter import AnkiNote, MappingError, Mappings, adapt, load_mappings
from scripts.anki_connect import AnkiConnect, AnkiConnectError
from scripts.card_schema import CardValidationError, load_facts
from scripts.config import ConfigError, load_config
from scripts.genanki_export import export_apkg
from scripts.media import bundled_font_paths, unique_media_paths
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
    mappings: Mappings | None = None,
    target_models: dict[str, str] | None = None,
    default_deck: str | None = None,
    auto_tag: str | None = None,
) -> ImportReport:
    """Import approved Facts, preferring AnkiConnect with a .apkg fallback.

    Configured external mappings apply on the live AnkiConnect path. The .apkg
    fallback builds the bundled MONO types; native image occlusion is live-only.
    """
    jsonl_path = Path(jsonl_path)
    facts = load_facts(
        jsonl_path,
        default_deck=default_deck,
        auto_tag=auto_tag,
    )

    if client is None:
        client = AnkiConnect()

    if client.is_available():
        notes = [
            adapt(
                fact,
                mappings,
                target_models=target_models,
                media_root=jsonl_path.parent,
            )
            for fact in facts
        ]
        decks = list(dict.fromkeys(n.deck for n in notes))  # distinct, ordered
        bundled = _used_note_types(notes, note_types)
        client.ensure_note_types(bundled)
        client.ensure_models_exist(
            note.model for note in notes if note.model not in note_types
        )
        note_media = [media for note in notes for media in note.media]
        fonts = bundled_font_paths() if bundled else []
        client.store_media_files(unique_media_paths([*fonts, *note_media]))
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

    # Fallback: Anki isn't running — write a MONO package to import manually.
    if any(fact.type == "image_occlusion" for fact in facts):
        raise RuntimeError(
            "native image occlusion requires a live AnkiConnect import"
        )
    notes = [adapt(fact, media_root=jsonl_path.parent) for fact in facts]
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
    parser.add_argument("--sync", action=argparse.BooleanOptionalAction, default=None,
                        help="Force/skip AnkiWeb sync (default: config.toml).")
    parser.add_argument("--url", default=None,
                        help="AnkiConnect URL (default: config.toml or :8765).")
    parser.add_argument("--config", default="config.toml",
                        help="Path to config.toml (optional; defaults apply).")
    parser.add_argument("--mappings", default="mappings.toml",
                        help="Path to mappings.toml for note-type interop.")
    parser.add_argument("--apkg-out", default=None,
                        help="Override the .apkg fallback path.")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        mappings = load_mappings(args.mappings)
        url = args.url or config.ankiconnect_url
        sync = args.sync if args.sync is not None else config.sync_after_import

        report = import_cards(
            args.jsonl, client=AnkiConnect(url), sync=sync,
            apkg_out=args.apkg_out, mappings=mappings,
            target_models=config.target_note_types,
            default_deck=config.default_deck,
            auto_tag=config.auto_tag,
        )
    except (
        AnkiConnectError,
        CardValidationError,
        ConfigError,
        FileNotFoundError,
        MappingError,
        RuntimeError,
        ValueError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(_format_summary(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
