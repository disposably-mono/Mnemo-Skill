import csv

import pytest

from scripts.import_refined_csv import (
    BASIC_MODEL,
    CLOZE_MODEL,
    PRESET_NAME,
    REFINED_BASIC,
    REFINED_CLOZE,
    REFINED_TYPED,
    TYPED_MODEL,
    apply_legacy_preset,
    existing_card_ids,
    import_refined_csv,
    load_notes,
)


FIELDS = [
    "Front", "Back", "Extra", "Mnemonic", "CardType", "Tags", "CardID",
    "Topic", "Source", "ImageURL", "ImageAlt", "KnowledgeKind", "Origin",
    "ObjectiveIDs",
]


def _write(path, rows, fields=FIELDS):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_refined_csv_routes_exact_answers_to_native_typed_model(tmp_path):
    path = tmp_path / "cards.csv"
    _write(path, [{
        "Front": "What is the formula for ROI?",
        "Back": "net profit / investment cost",
        "Extra": "Explanation: ROI compares return with cost.",
        "CardType": "typed",
        "Tags": "finance",
        "CardID": "roi-1",
        "Topic": "Metrics",
        "Source": "lecture.pdf p.2",
        "KnowledgeKind": "formula",
        "Origin": "source",
        "ObjectiveIDs": "objective-roi",
    }])

    notes, media = load_notes(path, "Course")

    assert media == []
    assert notes[0].model == TYPED_MODEL
    assert notes[0].fields["Prompt"] == "What is the formula for ROI?"
    assert notes[0].fields["Answer"] == "net profit / investment cost"
    assert "mnemo-kind-formula" in notes[0].tags
    assert "mnemo-objective-objective-roi" in notes[0].tags


def test_refined_csv_loads_basic_cloze_and_local_media(tmp_path):
    image = tmp_path / "diagram.png"
    image.write_bytes(b"png")
    path = tmp_path / "cards.csv"
    _write(path, [
        {"Front": "Question?", "Back": "Answer", "Extra": "Explanation: x",
         "CardType": "qa", "Tags": "one", "CardID": "1", "ImageURL": image.name},
        {"Front": "A {{c1::cloze}}", "Back": "cloze", "Extra": "Explanation: y",
         "CardType": "cloze", "Tags": "two", "CardID": "2"},
    ])

    notes, media = load_notes(path, "Deck")

    assert [note.model for note in notes] == [BASIC_MODEL, CLOZE_MODEL]
    assert notes[0].fields["Front"] == "Question?"
    assert notes[1].fields["Text"] == "A {{c1::cloze}}"
    assert media == [image]


def test_refined_csv_rejects_missing_fields_ids_and_media(tmp_path):
    path = tmp_path / "bad.csv"
    _write(path, [], fields=["Front"])
    with pytest.raises(ValueError, match="missing required"):
        load_notes(path, "Deck")

    _write(path, [{"Front": "Q", "Back": "A", "CardType": "qa"}])
    with pytest.raises(ValueError, match="CardID"):
        load_notes(path, "Deck")

    _write(path, [{"Front": "Q", "Back": "A", "CardType": "qa",
                   "CardID": "1", "ImageURL": "missing.png"}])
    with pytest.raises(FileNotFoundError):
        load_notes(path, "Deck")


class FakeResult:
    added = [100]
    skipped = 0


class FakeClient:
    def __init__(self):
        self.synced = False
        self.notes = []
        self.config = {
            "id": 7,
            "name": "Existing",
            "new": {"delays": [], "ints": [], "initialFactor": 0, "perDay": 0, "order": 1},
        }

    def is_available(self):
        return True

    def ensure_note_types(self, note_types):
        assert {item.name for item in note_types} == {
            REFINED_BASIC.name, REFINED_CLOZE.name, REFINED_TYPED.name,
        }

    def ensure_deck(self, deck):
        self.deck = deck

    def find_notes(self, query):
        return [1, 2] if "Existing" in query else []

    def store_media_files(self, paths):
        return [path.name for path in paths]

    def add_notes(self, notes):
        self.notes.extend(notes)
        return FakeResult()

    def sync(self):
        self.synced = True

    def _invoke(self, action, **params):
        if action == "modelFieldNames":
            models = {
                REFINED_BASIC.name: list(REFINED_BASIC.fields),
                REFINED_CLOZE.name: list(REFINED_CLOZE.fields),
                REFINED_TYPED.name: list(REFINED_TYPED.fields),
            }
            return models[params["modelName"]]
        if action == "notesInfo":
            return [
                {"fields": {"CardID": {"value": "known"}}},
                {"fields": {"CardID": "ignored"}},
            ]
        if action == "getDeckConfig":
            return self.config
        if action == "cloneDeckConfigId":
            return 9
        if action in {"setDeckConfigId", "saveDeckConfig"}:
            return True
        raise AssertionError(action)


def test_existing_ids_preset_and_full_refined_import(tmp_path):
    client = FakeClient()
    assert existing_card_ids(client, "Existing") == {"known"}
    assert existing_card_ids(client, "Empty") == set()

    preset_id = apply_legacy_preset(client, "Deck")
    assert preset_id == 9
    assert client.config["new"]["perDay"] == 20
    client.config["name"] = PRESET_NAME
    assert apply_legacy_preset(client, "Deck") == 7
    client.config["name"] = "Existing"

    path = tmp_path / "cards.csv"
    _write(path, [{"Front": "Q", "Back": "A", "Extra": "Explanation: x",
                   "CardType": "qa", "CardID": "new"}])
    report, assigned = import_refined_csv(path, "Course", client=client, sync=True)

    assert assigned == 9
    assert report.added == 1 and report.skipped == 0
    assert report.synced is True and client.synced is True
    assert client.notes[0].fields["CardID"] == "new"
