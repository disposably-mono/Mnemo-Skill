#!/usr/bin/env python3
"""Import a Mnemo refined CSV into a dedicated Anki deck via AnkiConnect."""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.adapter import AnkiNote
from scripts.anki_connect import AnkiConnect, AnkiConnectError
from scripts.note_types import CardTemplate, MONO_CSS, NoteType


BASIC_MODEL = "MONO Refined"
CLOZE_MODEL = "MONO Refined Cloze"
TYPED_MODEL = "MONO Refined Type"
PRESET_NAME = "Mnemo Refined Legacy SM-2"
REQUIRED_FIELDS = ("Front", "Back", "Extra", "Mnemonic", "CardType", "Tags", "CardID")

_DETAILS = """
{{#Extra}}<div class="refined-block"><div class="mono-label">Explanation</div>{{Extra}}</div>{{/Extra}}
{{#Mnemonic}}<div class="refined-block mnemonic"><div class="mono-label">Mnemonic</div>{{Mnemonic}}</div>{{/Mnemonic}}
{{#Topic}}<div class="source">Topic: {{Topic}}</div>{{/Topic}}
{{#Source}}<div class="source">Source: {{Source}}</div>{{/Source}}
{{#CardID}}<div class="source">ID: {{CardID}}</div>{{/CardID}}
"""

REFINED_CSS = MONO_CSS + """
.refined-block {
  margin-top: 18px;
  padding: 12px 14px;
  border-left: 3px solid var(--accent);
  background: var(--bg-2);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  font-size: 16px;
}
.refined-block.mnemonic { border-left-color: var(--highlight); }
"""

REFINED_BASIC = NoteType(
    name=BASIC_MODEL,
    fields=(
        "Front", "Back", "Extra", "Mnemonic", "CardType", "Topic",
        "Source", "ImageURL", "ImageAlt", "CardID",
    ),
    templates=(
        CardTemplate(
            name="Recall",
            qfmt=(
                '<div class="mono-label">{{CardType}}</div>'
                '<div class="mono-q">{{Front}}</div>'
            ),
            afmt=(
                '{{FrontSide}}<hr id="answer">'
                '<div class="mono-a">{{Back}}</div>' + _DETAILS
            ),
        ),
    ),
    css=REFINED_CSS,
)

REFINED_CLOZE = NoteType(
    name=CLOZE_MODEL,
    fields=(
        "Text", "Back", "Extra", "Mnemonic", "CardType", "Topic",
        "Source", "ImageURL", "ImageAlt", "CardID",
    ),
    templates=(
        CardTemplate(
            name="Cloze",
            qfmt=(
                '<div class="mono-label">cloze</div>'
                '<div class="mono-a">{{cloze:Text}}</div>'
            ),
            afmt=(
                '<div class="mono-label">cloze</div>'
                '<div class="mono-a">{{cloze:Text}}</div>'
                '<hr id="answer"><div class="mono-a">{{Back}}</div>' + _DETAILS
            ),
        ),
    ),
    css=REFINED_CSS,
    is_cloze=True,
)

REFINED_TYPED = NoteType(
    name=TYPED_MODEL,
    fields=(
        "Prompt", "Answer", "Extra", "Mnemonic", "CardType", "Topic",
        "Source", "CardID",
    ),
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
                '<div class="mono-a">{{Answer}}</div>' + _DETAILS
            ),
        ),
    ),
    css=REFINED_CSS,
)


@dataclass(frozen=True)
class RefinedImportReport:
    deck: str
    added: int
    skipped: int
    media: tuple[str, ...]
    preset: str
    synced: bool


def load_notes(csv_path: Path, deck: str) -> tuple[list[AnkiNote], list[Path]]:
    notes: list[AnkiNote] = []
    media: dict[Path, None] = {}
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in REQUIRED_FIELDS if field not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"CSV is missing required fields: {', '.join(missing)}")
        for line_number, row in enumerate(reader, start=2):
            card_id = (row.get("CardID") or "").strip()
            if not card_id:
                raise ValueError(f"line {line_number}: CardID is required")
            image_url = (row.get("ImageURL") or "").strip()
            if image_url and "://" not in image_url:
                image_path = csv_path.parent / image_url
                if not image_path.exists():
                    raise FileNotFoundError(image_path)
                media[image_path] = None
            common = {
                "Back": row.get("Back", ""),
                "Extra": row.get("Extra", ""),
                "Mnemonic": row.get("Mnemonic", ""),
                "CardType": row.get("CardType", ""),
                "Topic": row.get("Topic", ""),
                "Source": row.get("Source", ""),
                "ImageURL": image_url,
                "ImageAlt": row.get("ImageAlt", ""),
                "CardID": card_id,
            }
            card_type = row.get("CardType")
            is_cloze = card_type == "cloze"
            is_typed = card_type == "typed"
            if is_typed:
                fields = {
                    "Prompt": row.get("Front", ""),
                    "Answer": row.get("Back", ""),
                    "Extra": common["Extra"],
                    "Mnemonic": common["Mnemonic"],
                    "CardType": common["CardType"],
                    "Topic": common["Topic"],
                    "Source": common["Source"],
                    "CardID": common["CardID"],
                }
            else:
                fields = ({"Text": row.get("Front", "") } | common) if is_cloze else ({"Front": row.get("Front", "")} | common)
            tags = [
                *(row.get("Tags") or "").split(),
                "refined",
                "mnemo-refined",
                f"mnemo-id-{card_id}",
                *(
                    [f"mnemo-kind-{row['KnowledgeKind']}"]
                    if (row.get("KnowledgeKind") or "").strip()
                    else []
                ),
                *(
                    [f"mnemo-origin-{row['Origin']}"]
                    if (row.get("Origin") or "").strip()
                    else []
                ),
                *(f"mnemo-objective-{value}" for value in (row.get("ObjectiveIDs") or "").split()),
            ]
            notes.append(
                AnkiNote(
                    model=TYPED_MODEL if is_typed else (CLOZE_MODEL if is_cloze else BASIC_MODEL),
                    deck=deck,
                    fields=fields,
                    tags=list(dict.fromkeys(tags)),
                )
            )
    return notes, list(media)


def existing_card_ids(client: AnkiConnect, deck: str) -> set[str]:
    note_ids = client.find_notes(f'deck:"{deck}"')
    if not note_ids:
        return set()
    ids: set[str] = set()
    for start in range(0, len(note_ids), 500):
        for info in client._invoke("notesInfo", notes=note_ids[start:start + 500]):
            field = info.get("fields", {}).get("CardID", {})
            value = field.get("value", "") if isinstance(field, dict) else ""
            if value:
                ids.add(value)
    return ids


def apply_legacy_preset(client: AnkiConnect, deck: str, preset_id: int | None = None) -> int:
    client.ensure_deck(deck)
    if preset_id is None:
        current = client._invoke("getDeckConfig", deck=deck)
        if current.get("name") == PRESET_NAME:
            preset_id = int(current["id"])
        else:
            preset_id = int(
                client._invoke(
                    "cloneDeckConfigId",
                    name=PRESET_NAME,
                    cloneFrom=str(current["id"]),
                )
            )
    if not client._invoke("setDeckConfigId", decks=[deck], configId=preset_id):
        raise AnkiConnectError(f"could not assign preset {preset_id} to {deck}")
    config = client._invoke("getDeckConfig", deck=deck)
    config["new"]["delays"] = [10.0, 1440.0]
    config["new"]["ints"] = [3, 7, 0]
    config["new"]["initialFactor"] = 2500
    config["new"]["perDay"] = 20
    config["new"]["order"] = 0
    if not client._invoke("saveDeckConfig", config=config):
        raise AnkiConnectError(f"could not save preset for {deck}")
    return preset_id


def import_refined_csv(
    csv_path: str | Path,
    deck: str,
    *,
    client: AnkiConnect | None = None,
    sync: bool = False,
    preset_id: int | None = None,
) -> tuple[RefinedImportReport, int]:
    csv_path = Path(csv_path)
    client = client or AnkiConnect()
    if not client.is_available():
        raise AnkiConnectError("AnkiConnect is unavailable; open Anki and retry")
    client.ensure_note_types((REFINED_BASIC, REFINED_CLOZE, REFINED_TYPED))
    expected = {
        REFINED_BASIC.name: list(REFINED_BASIC.fields),
        REFINED_CLOZE.name: list(REFINED_CLOZE.fields),
        REFINED_TYPED.name: list(REFINED_TYPED.fields),
    }
    for model, fields in expected.items():
        actual = client._invoke("modelFieldNames", modelName=model)
        if actual != fields:
            raise AnkiConnectError(f"{model} fields differ from the refined schema")
    preset_id = apply_legacy_preset(client, deck, preset_id)
    notes, media_paths = load_notes(csv_path, deck)
    stored = tuple(client.store_media_files(media_paths))
    known_ids = existing_card_ids(client, deck)
    pending = [note for note in notes if note.fields["CardID"] not in known_ids]
    result = client.add_notes(pending) if pending else None
    added = len(result.added) if result else 0
    skipped = len(notes) - len(pending) + (result.skipped if result else 0)
    if sync:
        client.sync()
    return RefinedImportReport(deck, added, skipped, stored, PRESET_NAME, sync), preset_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--deck", required=True)
    parser.add_argument("--url", default="http://localhost:8765")
    parser.add_argument("--sync", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report, _ = import_refined_csv(
            args.csv,
            args.deck,
            client=AnkiConnect(args.url),
            sync=args.sync,
        )
    except (AnkiConnectError, FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(
        f"{report.deck}: {report.added} added, {report.skipped} skipped; "
        f"preset={report.preset}, media={len(report.media)}, synced={report.synced}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
