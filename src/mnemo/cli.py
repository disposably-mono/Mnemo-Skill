"""The mnemo CLI: one entry point, subcommands for each pipeline stage.

mnemo ingest <source> [--ocr] [--extract-images DIR]
mnemo draft <source> -o cards.csv [--deferred deferred.md]
mnemo audit cards.csv
mnemo import cards.csv --deck DECK [--config config.toml] [--apkg-out deck.apkg]
mnemo export-note-types [--config config.toml]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mnemo.anki.connect import AnkiConnect, AnkiConnectError
from mnemo.anki.export import export_apkg
from mnemo.anki.note_types import MONO_NOTE_TYPES, note_type_for, render_fields
from mnemo.audit import build_report
from mnemo.card import Card, read_cards, write_cards
from mnemo.config import Config, load_config
from mnemo.draft import draft_cards, write_deferred
from mnemo.ingest import ingest


def cmd_ingest(source: str | Path, *, ocr: bool = False, extract_images: Path | None = None) -> int:
    for chunk in ingest(source, ocr=ocr, extract_images=extract_images):
        print(f"--- {chunk.source} ---")
        print(chunk.text)
        print()
    return 0


def cmd_draft(source: str | Path, cards_out: Path, deferred_out: Path | None = None) -> int:
    chunks = ingest(source)
    cards, deferred = draft_cards(chunks)
    write_cards(cards_out, cards)
    # Named after cards_out's stem (not a fixed "deferred.md") so drafting
    # multiple sources into the same directory doesn't silently clobber a
    # previous run's deferred units.
    default_deferred = cards_out.with_name(f"{cards_out.stem}.deferred.md")
    write_deferred(deferred_out or default_deferred, deferred)
    print(f"Drafted {len(cards)} card(s), deferred {len(deferred)} unit(s) -> {cards_out}")
    return 0


def cmd_audit(cards_csv: Path) -> int:
    cards = read_cards(cards_csv)
    report = build_report(cards)
    print(f"{report.status}: {cards_csv}")
    print(f"Cards: {report.card_count} | Errors: {report.errors} | Warnings: {report.warnings}")
    for violation in report.violations:
        card = f" card={violation.card_id}" if violation.card_id else ""
        print(f"- {violation.level.upper()} {violation.code}{card}: {violation.message}")
    return 0 if report.status == "PASS" else 1


def cmd_import(
    cards_csv: Path, *, deck: str, config_path: Path | None, apkg_out: Path | None
) -> int:
    config = load_config(config_path)
    cards = read_cards(cards_csv)
    ankiconnect = AnkiConnect(url=config.ankiconnect_url)
    if ankiconnect.is_available():
        return _import_via_ankiconnect(cards, deck, config, ankiconnect)
    return _import_via_apkg(cards, deck, apkg_out or cards_csv.with_suffix(".apkg"))


def _import_via_ankiconnect(
    cards: list[Card], deck: str, config: Config, ankiconnect: AnkiConnect
) -> int:
    ankiconnect.ensure_deck(deck)
    ankiconnect.ensure_note_types(MONO_NOTE_TYPES.values())
    by_model: dict[str, list[Card]] = {}
    for card in cards:
        model = note_type_for(card.card_type).name
        by_model.setdefault(model, []).append(card)
    total_added = 0
    skipped_cards: list[Card] = []
    for model, model_cards in by_model.items():
        note_type = MONO_NOTE_TYPES[model]
        fields_list = [render_fields(card, note_type) for card in model_cards]
        tags_list = [card.tags for card in model_cards]
        result = ankiconnect.add_notes(
            deck=deck, model=model, fields_list=fields_list, tags_list=tags_list,
        )
        total_added += len(result.added)
        # Skipped cards must stay identifiable, not just counted -- the
        # product design never fabricates or silently discards; the user
        # needs to know *which* card AnkiConnect refused (usually a
        # duplicate) to review it.
        skipped_cards.extend(
            card for card, nid in zip(model_cards, result.results) if nid is None
        )
    if config.sync_after_import:
        ankiconnect.sync()
    print(
        f"Imported via AnkiConnect: {total_added} added, "
        f"{len(skipped_cards)} skipped -> {deck}"
    )
    for card in skipped_cards:
        print(f"  SKIPPED (likely duplicate): {card.front!r} [{card.source or 'no source'}]")
    return 0


def _import_via_apkg(cards: list[Card], deck: str, apkg_out: Path) -> int:
    result = export_apkg([(card, deck) for card in cards], apkg_out)
    print(f"AnkiConnect unavailable; exported {result.count} card(s) -> {result.path}")
    return 0


def cmd_export_note_types(config_path: Path | None) -> int:
    config = load_config(config_path)
    ankiconnect = AnkiConnect(url=config.ankiconnect_url)
    if not ankiconnect.is_available():
        print("AnkiConnect is not reachable; start Anki desktop and try again.", file=sys.stderr)
        return 1
    created = ankiconnect.ensure_note_types(MONO_NOTE_TYPES.values())
    print(f"Created: {created or '(none, all up to date)'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mnemo", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Normalize a source into text chunks.")
    ingest_parser.add_argument("source", type=Path)
    ingest_parser.add_argument("--ocr", action="store_true")
    ingest_parser.add_argument("--extract-images", type=Path, metavar="DIR")

    draft_parser = subparsers.add_parser("draft", help="Draft cards from a source.")
    draft_parser.add_argument("source", type=Path)
    draft_parser.add_argument("--output", "-o", type=Path, required=True, dest="cards_out")
    draft_parser.add_argument("--deferred", type=Path, default=None)

    audit_parser = subparsers.add_parser("audit", help="Audit a cards CSV against the rubric.")
    audit_parser.add_argument("cards_csv", type=Path)

    import_parser = subparsers.add_parser("import", help="Import a cards CSV into Anki.")
    import_parser.add_argument("cards_csv", type=Path)
    import_parser.add_argument("--deck", required=True)
    import_parser.add_argument("--config", type=Path, default=None, dest="config_path")
    import_parser.add_argument("--apkg-out", type=Path, default=None)

    export_nt_parser = subparsers.add_parser(
        "export-note-types", help="Install/update the MONO note types in Anki."
    )
    export_nt_parser.add_argument("--config", type=Path, default=None, dest="config_path")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _dispatch(args)
    except FileNotFoundError as exc:
        print(f"File not found: {exc}", file=sys.stderr)
        return 1
    except (AnkiConnectError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "ingest":
        return cmd_ingest(args.source, ocr=args.ocr, extract_images=args.extract_images)
    if args.command == "draft":
        return cmd_draft(args.source, args.cards_out, args.deferred)
    if args.command == "audit":
        return cmd_audit(args.cards_csv)
    if args.command == "import":
        return cmd_import(
            args.cards_csv, deck=args.deck, config_path=args.config_path, apkg_out=args.apkg_out,
        )
    if args.command == "export-note-types":
        return cmd_export_note_types(args.config_path)
    raise AssertionError(f"unhandled command: {args.command!r}")  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
