"""The mnemo CLI: one entry point, subcommands for each pipeline stage.

mnemo ingest <source> [--ocr] [--lang eng] [--extract-images DIR]
mnemo draft <source> --deck DECK -o deck.mnemo.yaml [--directions MODE]
mnemo audit deck.mnemo.yaml
mnemo import deck.mnemo.yaml [--config config.toml] [--apkg-out deck.apkg] [--update-existing]
mnemo export-note-types [--config config.toml]

--lang is a Tesseract language code (default "eng"); use "fil" for Filipino/
Tagalog, or "eng+fil" for mixed-language scanned PDFs. Only affects --ocr.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

from mnemo.anki.connect import AnkiConnect, AnkiConnectError
from mnemo.anki.export import export_apkg
from mnemo.anki.note_types import MONO_NOTE_TYPES, note_type_for, render_fields
from mnemo.audit import build_report
from mnemo.card import Card
from mnemo.config import Config, load_config
from mnemo.deck import Deck, cards_for_import, read_deck, write_deck
from mnemo.draft import draft_cards, write_deferred
from mnemo.ingest import ingest


def cmd_ingest(
    source: str | Path,
    *,
    ocr: bool = False,
    extract_images: Path | None = None,
    language: str = "eng",
    pages: tuple[int, int] | None = None,
    prose_language: str | None = None,
) -> int:
    chunks = ingest(
        source, ocr=ocr, extract_images=extract_images, language=language,
        pages=pages, prose_language=prose_language,
    )
    for chunk in chunks:
        print(f"--- {chunk.source} ---")
        print(chunk.text)
        print()
    return 0


def cmd_draft(
    source: str | Path,
    cards_out: Path,
    deferred_out: Path | None = None,
    *,
    deck: str,
    directions: str = "term-to-definition",
    ocr: bool = False,
    language: str = "eng",
    pages: tuple[int, int] | None = None,
    prose_language: str | None = None,
) -> int:
    _require_deck_manifest_path(cards_out)
    chunks = ingest(
        source, ocr=ocr, language=language, pages=pages, prose_language=prose_language,
    )
    cards, deferred = draft_cards(chunks, directions=directions)
    context = (deck, str(Path(source).resolve()), directions, ocr, language, pages, prose_language)
    context_hash = hashlib.sha256(
        json.dumps(context, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    identified_cards = [
        replace(card, card_id=f"draft-{context_hash}-{index:04d}")
        for index, card in enumerate(cards, start=1)
    ]
    write_deck(cards_out, Deck(name=deck, cards=identified_cards))
    # Named after cards_out's stem (not a fixed "deferred.md") so drafting
    # multiple sources into the same directory doesn't silently clobber a
    # previous run's deferred units.
    default_deferred = cards_out.with_name(f"{cards_out.stem}.deferred.md")
    write_deferred(deferred_out or default_deferred, deferred)
    print(f"Drafted {len(cards)} card(s), deferred {len(deferred)} unit(s) -> {cards_out}")
    return 0


def cmd_audit(deck_path: Path) -> int:
    _require_deck_manifest_path(deck_path)
    deck = read_deck(deck_path)
    report = build_report(deck.cards)
    print(f"{report.status}: {deck_path}")
    print(f"Cards: {report.card_count} | Errors: {report.errors} | Warnings: {report.warnings}")
    for violation in report.violations:
        card = f" card={violation.card_id}" if violation.card_id else ""
        print(f"- {violation.level.upper()} {violation.code}{card}: {violation.message}")
    return 0 if report.status == "PASS" else 1


def cmd_import(
    deck_path: Path, *, config_path: Path | None, apkg_out: Path | None,
    update_existing: bool = False,
) -> int:
    _require_deck_manifest_path(deck_path)
    config = load_config(config_path)
    deck = read_deck(deck_path)
    cards = cards_for_import(deck)
    ankiconnect = AnkiConnect(url=config.ankiconnect_url)
    if ankiconnect.is_available():
        return _import_via_ankiconnect(
            cards, deck.name, config, ankiconnect, update_existing=update_existing,
        )
    default_apkg = deck_path.with_name(deck_path.name.removesuffix(".mnemo.yaml") + ".apkg")
    return _import_via_apkg(cards, deck.name, apkg_out or default_apkg)


def _require_deck_manifest_path(path: Path) -> None:
    if not Path(path).name.endswith(".mnemo.yaml"):
        raise ValueError("only .mnemo.yaml deck manifests are supported")


def _prepare_ankiconnect_import(
    cards: list[Card], ankiconnect: AnkiConnect, update_existing: bool,
) -> dict[str, list[tuple[Card, dict[str, str], int | None]]]:
    if update_existing and any(not card.card_id or not card.card_id.strip() for card in cards):
        raise ValueError("--update-existing requires a non-empty CardID for every card")
    by_model: dict[str, list[tuple[Card, dict[str, str], int | None]]] = {}
    for card in cards:
        model = note_type_for(card.card_type).name
        fields = render_fields(card, MONO_NOTE_TYPES[model])
        note_id = (
            ankiconnect.find_note_id_by_card_id(card.card_id, model)
            if update_existing else None
        )
        by_model.setdefault(model, []).append((card, fields, note_id))
    return by_model


def _import_via_ankiconnect(
    cards: list[Card], deck: str, config: Config, ankiconnect: AnkiConnect,
    *, update_existing: bool = False,
) -> int:
    by_model = _prepare_ankiconnect_import(cards, ankiconnect, update_existing)
    ankiconnect.ensure_deck(deck)
    ankiconnect.ensure_note_types(MONO_NOTE_TYPES.values())
    total_added = 0
    total_updated = 0
    skipped_cards: list[Card] = []
    for model, model_entries in by_model.items():
        for _, fields, note_id in model_entries:
            if note_id is not None:
                ankiconnect.update_note_fields(note_id, fields)
                total_updated += 1
        to_add = [
            (card, fields) for card, fields, note_id in model_entries
            if note_id is None
        ]
        if not to_add:
            continue
        result = ankiconnect.add_notes(
            deck=deck, model=model, fields_list=[fields for _, fields in to_add],
            tags_list=[card.tags for card, _ in to_add],
        )
        total_added += len(result.added)
        # Skipped cards must stay identifiable, not just counted -- the
        # product design never fabricates or silently discards; the user
        # needs to know *which* card AnkiConnect refused (usually a
        # duplicate) to review it.
        skipped_cards.extend(
            card for (card, _), nid in zip(to_add, result.results) if nid is None
        )
    if config.sync_after_import:
        ankiconnect.sync()
    counts = f"{total_added} added, "
    if update_existing:
        counts += f"{total_updated} updated, "
    print(f"Imported via AnkiConnect: {counts}{len(skipped_cards)} skipped -> {deck}")
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


def _parse_page_range(value: str) -> tuple[int, int]:
    parts = value.replace(":", "-").split("-")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"invalid page range {value!r}, expected START-END")
    try:
        start, end = int(parts[0]), int(parts[1])
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid page range {value!r}, expected START-END")
    if start < 1 or end < start:
        raise argparse.ArgumentTypeError(f"invalid page range {value!r}: start must be >=1, end >= start")
    return (start, end)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mnemo", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Normalize a source into text chunks.")
    ingest_parser.add_argument("source", type=Path)
    ingest_parser.add_argument("--ocr", action="store_true")
    ingest_parser.add_argument("--lang", default="eng", dest="language")
    ingest_parser.add_argument("--extract-images", type=Path, metavar="DIR")
    ingest_parser.add_argument("--pages", type=_parse_page_range, metavar="START-END")
    ingest_parser.add_argument(
        "--prose-lang", choices=("fil", "eng"), default=None, dest="prose_language",
        help="Keep only PDF pages confidently classified as this prose language.",
    )

    draft_parser = subparsers.add_parser("draft", help="Draft a YAML deck manifest from a source.")
    draft_parser.add_argument("source", type=Path)
    draft_parser.add_argument(
        "--output", "-o", type=Path, required=True, dest="cards_out",
        metavar="DECK.mnemo.yaml", help="Output YAML deck manifest (must end in .mnemo.yaml).",
    )
    draft_parser.add_argument("--deck", required=True, help="Destination deck name in the manifest.")
    draft_parser.add_argument(
        "--directions", choices=("term-to-definition", "definition-to-term", "both"),
        default="term-to-definition",
    )
    draft_parser.add_argument("--deferred", type=Path, default=None)
    draft_parser.add_argument("--ocr", action="store_true")
    draft_parser.add_argument("--lang", default="eng", dest="language")
    draft_parser.add_argument("--pages", type=_parse_page_range, metavar="START-END")
    draft_parser.add_argument(
        "--prose-lang", choices=("fil", "eng"), default=None, dest="prose_language",
        help="Keep only PDF pages confidently classified as this prose language.",
    )

    audit_parser = subparsers.add_parser("audit", help="Audit a deck manifest against the rubric.")
    audit_parser.add_argument("deck_path", type=Path, metavar="DECK.mnemo.yaml")

    import_parser = subparsers.add_parser("import", help="Import a deck manifest into Anki.")
    import_parser.add_argument("deck_path", type=Path, metavar="DECK.mnemo.yaml")
    import_parser.add_argument("--config", type=Path, default=None, dest="config_path")
    import_parser.add_argument("--apkg-out", type=Path, default=None)
    import_parser.add_argument("--update-existing", action="store_true")

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
        return cmd_ingest(
            args.source, ocr=args.ocr, extract_images=args.extract_images,
            language=args.language, pages=args.pages, prose_language=args.prose_language,
        )
    if args.command == "draft":
        return cmd_draft(
            args.source, args.cards_out, args.deferred,
            deck=args.deck, directions=args.directions,
            ocr=args.ocr, language=args.language,
            pages=args.pages, prose_language=args.prose_language,
        )
    if args.command == "audit":
        return cmd_audit(args.deck_path)
    if args.command == "import":
        return cmd_import(
            args.deck_path, config_path=args.config_path, apkg_out=args.apkg_out,
            update_existing=args.update_existing,
        )
    if args.command == "export-note-types":
        return cmd_export_note_types(args.config_path)
    raise AssertionError(f"unhandled command: {args.command!r}")  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
