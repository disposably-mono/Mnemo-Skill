#!/usr/bin/env python3
"""Import a Mnemo refined CSV into a dedicated Anki deck via AnkiConnect.

Each CSV row is converted into a validated Fact (``row_to_fact``) and rendered
through the shared note-type adapter (``scripts.adapter.adapt``) using the
``REFINED_MAPPINGS`` field templates; only presentation-only CSV columns are
copied into the note afterwards (see ``_apply_passthrough``).
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mnemo.anki.adapter import AnkiNote, Mappings, adapt
from mnemo.anki.anki_connect import AnkiConnect, AnkiConnectError
from mnemo.core.card_schema import CardValidationError, Fact
from mnemo.anki.note_types import CardTemplate, MONO_CSS, NoteType


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

# Image-supported recall: the image renders on the answer side only, so
# text-only cards (no ImageURL) are visually unaffected.
_IMAGE_BLOCK = (
    '{{#ImageURL}}<div class="refined-image"><img src="{{ImageURL}}" alt="{{ImageAlt}}"></div>{{/ImageURL}}'
)

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
.refined-image { margin-top: 18px; }
.refined-image img { max-width: 100%; border-radius: var(--radius-md); display: block; }
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
                '<div class="mono-a">{{Back}}</div>' + _IMAGE_BLOCK + _DETAILS
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
                '<hr id="answer"><div class="mono-a">{{Back}}</div>'
                + _IMAGE_BLOCK + _DETAILS
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


# How a refined Fact renders into the refined note types: a plain adapter
# mappings dict, so the CSV path shares the exact rendering machinery used by
# the JSONL/Fact path (scripts.adapter.adapt).
REFINED_MAPPINGS: Mappings = {
    "qa": {BASIC_MODEL: {
        "Front": "{front}", "Back": "{back}", "Extra": "{extra}",
        "Mnemonic": "{mnemonic}", "Topic": "{topic}", "Source": "{source}",
        "CardID": "{fact_id}",
    }},
    "cloze": {CLOZE_MODEL: {
        "Text": "{text}", "Extra": "{extra}", "Mnemonic": "{mnemonic}",
        "Topic": "{topic}", "Source": "{source}", "CardID": "{fact_id}",
    }},
    "typed": {TYPED_MODEL: {
        "Prompt": "{prompt}", "Answer": "{answer}", "Extra": "{extra}",
        "Mnemonic": "{mnemonic}", "Topic": "{topic}", "Source": "{source}",
        "CardID": "{fact_id}",
    }},
}

_NOTE_TYPES_BY_MODEL = {
    note_type.name: note_type
    for note_type in (REFINED_BASIC, REFINED_CLOZE, REFINED_TYPED)
}

# Fact metadata read straight from optional CSV columns (validated by the
# Fact contract, so a hand-edited value fails with a clear per-line error).
_METADATA_COLUMNS = (
    ("KnowledgeUnitID", "knowledge_unit_id"),
    ("KnowledgeKind", "knowledge_kind"),
    ("Origin", "origin"),
)


def row_to_fact(row: dict[str, str], deck: str) -> Fact:
    """Convert one refined-CSV row into a validated Fact.

    CardType ``cloze``/``typed`` map to the matching Fact types; every other
    CardType (qa, reverse, image-supported, list, unknown) becomes ``qa``.
    Raises CardValidationError on any malformed value; the caller adds the
    CSV line number.
    """
    card_id = (row.get("CardID") or "").strip()
    if not card_id:
        raise CardValidationError("CardID is required")
    annotations = {
        "extra": row.get("Extra") or "",
        "mnemonic": row.get("Mnemonic") or "",
        "topic": row.get("Topic") or "",
    }
    card_type = (row.get("CardType") or "").strip()
    if card_type == "cloze":
        content = {"text": row.get("Front") or "", **annotations}
    elif card_type == "typed":
        content = {"prompt": row.get("Front") or "",
                   "answer": row.get("Back") or "", **annotations}
    else:
        card_type = "qa"
        content = {"front": row.get("Front") or "",
                   "back": row.get("Back") or "", **annotations}

    data: dict[str, object] = {
        "type": card_type,
        "content": content,
        "deck": deck,
        "id": card_id,
        "tags": _augmented_tags(row, card_id),
    }
    if (row.get("Source") or "").strip():
        data["source"] = row["Source"]
    for column, key in _METADATA_COLUMNS:
        if (row.get(column) or "").strip():
            data[key] = row[column].strip()
    for column, key in (("ObjectiveIDs", "objective_ids"),
                        ("PrerequisiteIDs", "prerequisite_ids")):
        values = (row.get(column) or "").split()
        if values:
            data[key] = values
    confidence = (row.get("Confidence") or "").strip()
    if confidence:
        try:
            data["confidence"] = float(confidence)
        except ValueError:
            raise CardValidationError(
                f"Confidence must be a number between 0 and 1, got {confidence!r}"
            ) from None
    return Fact.from_dict(data)


def _augmented_tags(row: dict[str, str], card_id: str) -> list[str]:
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
    return list(dict.fromkeys(tags))


def _collect_local_image(
    row: dict[str, str], base_dir: Path, media: dict[Path, None]
) -> str:
    """Register a CSV-local image for upload and return the field value."""
    image_url = (row.get("ImageURL") or "").strip()
    if image_url and "://" not in image_url:
        image_path = base_dir / image_url
        if not image_path.exists():
            raise FileNotFoundError(image_path)
        media[image_path] = None
        # AnkiConnect stores media flat by basename, so the field must
        # reference that basename rather than the CSV-relative path.
        image_url = image_path.name
    return image_url


def _apply_passthrough(note: AnkiNote, row: dict[str, str], image_url: str) -> None:
    """Copy presentation-only CSV columns into the rendered note.

    CardType, ImageURL, ImageAlt (and the cloze model's Back field) are
    verbatim CSV passthroughs with no semantic Fact representation, so instead
    of widening the Fact contract they are patched into the note that
    ``adapt`` produced. No templating happens here — this is not a second
    rendering path.
    """
    passthrough = {
        "CardType": row.get("CardType") or "",
        "ImageURL": image_url,
        "ImageAlt": row.get("ImageAlt") or "",
        "Back": row.get("Back") or "",
    }
    model_fields = _NOTE_TYPES_BY_MODEL[note.model].fields
    for name, value in passthrough.items():
        if name in model_fields and name not in note.fields:
            note.fields[name] = value


def load_notes(csv_path: Path, deck: str) -> tuple[list[AnkiNote], list[Path]]:
    notes: list[AnkiNote] = []
    media: dict[Path, None] = {}
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in REQUIRED_FIELDS if field not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"CSV is missing required fields: {', '.join(missing)}")
        for line_number, row in enumerate(reader, start=2):
            try:
                fact = row_to_fact(row, deck)
            except CardValidationError as exc:
                raise ValueError(f"line {line_number}: {exc}") from exc
            image_url = _collect_local_image(row, csv_path.parent, media)
            note = adapt(fact, mappings=REFINED_MAPPINGS)
            _apply_passthrough(note, row, image_url)
            notes.append(note)
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
