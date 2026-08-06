import csv

import pytest

from mnemo.core.card_schema import CardValidationError
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
    row_to_fact,
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


def test_local_image_field_rewritten_to_stored_basename(tmp_path):
    # BUG 4: ImageURL holds the CSV-relative path, but AnkiConnect stores
    # media flat by basename — the note field must be rewritten to match
    # what actually ends up in the Anki media folder.
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    image = img_dir / "diagram.png"
    image.write_bytes(b"png")
    path = tmp_path / "cards.csv"
    _write(path, [{
        "Front": "Q", "Back": "A", "CardType": "qa", "CardID": "1",
        "ImageURL": "images/diagram.png", "ImageAlt": "a diagram",
    }])

    notes, media = load_notes(path, "Deck")

    assert media == [image]
    assert notes[0].fields["ImageURL"] == "diagram.png"
    assert notes[0].fields["ImageAlt"] == "a diagram"


def test_remote_image_url_left_unchanged(tmp_path):
    path = tmp_path / "cards.csv"
    _write(path, [{
        "Front": "Q", "Back": "A", "CardType": "qa", "CardID": "1",
        "ImageURL": "https://example.com/diagram.png", "ImageAlt": "a diagram",
    }])

    notes, media = load_notes(path, "Deck")

    assert media == []
    assert notes[0].fields["ImageURL"] == "https://example.com/diagram.png"


def test_refined_basic_and_cloze_templates_render_the_image():
    for note_type in (REFINED_BASIC, REFINED_CLOZE):
        afmt = note_type.templates[0].afmt
        assert "{{ImageURL}}" in afmt, note_type.name
        assert "{{ImageAlt}}" in afmt, note_type.name
        assert "{{#ImageURL}}" in afmt, note_type.name


# --- row_to_fact ------------------------------------------------------------

def test_row_to_fact_maps_each_card_type():
    base = {"Front": "A {{c1::cloze}} question?", "Back": "An answer",
            "Extra": "why", "Mnemonic": "hook", "Topic": "T", "CardID": "x"}
    expected = {
        "cloze": ("cloze", {"text": "A {{c1::cloze}} question?"}),
        "typed": ("typed", {"prompt": "A {{c1::cloze}} question?",
                            "answer": "An answer"}),
        "qa": ("qa", {"front": "A {{c1::cloze}} question?", "back": "An answer"}),
        "reverse": ("qa", {}),
        "image-supported": ("qa", {}),
        "list": ("qa", {}),
        "": ("qa", {}),
        "unknown": ("qa", {}),
    }
    for card_type, (fact_type, content) in expected.items():
        fact = row_to_fact({**base, "CardType": card_type}, "Deck")
        assert fact.type == fact_type, card_type
        for key, value in content.items():
            assert fact.content[key] == value, card_type
        assert fact.content["extra"] == "why"
        assert fact.content["mnemonic"] == "hook"
        assert fact.content["topic"] == "T"
        assert fact.id == "x"
        assert fact.deck == "Deck"


def test_row_to_fact_carries_semantic_metadata():
    fact = row_to_fact({
        "Front": "Q?", "Back": "A", "CardType": "qa", "CardID": "roi-1",
        "Tags": "finance", "Source": "lecture.pdf p.2",
        "KnowledgeUnitID": "unit-roi", "KnowledgeKind": "formula",
        "Origin": "source", "ObjectiveIDs": "objective-roi",
        "PrerequisiteIDs": "unit-profit", "Confidence": "0.9",
    }, "Deck")
    assert fact.source == "lecture.pdf p.2"
    assert fact.knowledge_unit_id == "unit-roi"
    assert fact.knowledge_kind == "formula"
    assert fact.origin == "source"
    assert fact.objective_ids == ["objective-roi"]
    assert fact.prerequisite_ids == ["unit-profit"]
    assert fact.confidence == 0.9
    assert "finance" in fact.tags and "mnemo-kind-formula" in fact.tags


def test_row_to_fact_rejects_malformed_metadata():
    base = {"Front": "Q?", "Back": "A", "CardType": "qa", "CardID": "x"}
    with pytest.raises(CardValidationError, match="knowledge_kind"):
        row_to_fact({**base, "KnowledgeKind": "vibes"}, "Deck")
    with pytest.raises(CardValidationError, match="Confidence"):
        row_to_fact({**base, "Confidence": "high"}, "Deck")
    with pytest.raises(CardValidationError, match="CardID"):
        row_to_fact({"Front": "Q?", "Back": "A", "CardType": "qa"}, "Deck")


def test_malformed_metadata_surfaces_with_csv_line_number(tmp_path):
    path = tmp_path / "cards.csv"
    _write(path, [
        {"Front": "Q1", "Back": "A1", "CardType": "qa", "CardID": "1"},
        {"Front": "Q2", "Back": "A2", "CardType": "qa", "CardID": "2",
         "Origin": "not-a-real-origin"},
    ])
    with pytest.raises(ValueError, match="line 3.*origin"):
        load_notes(path, "Deck")


def test_image_supported_card_keeps_back_html(tmp_path):
    image = tmp_path / "diagram.png"
    image.write_bytes(b"png")
    back_html = 'See <b>the diagram</b> &amp; label the <i>atria</i>.'
    path = tmp_path / "cards.csv"
    _write(path, [{
        "Front": "Which chambers receive blood?", "Back": back_html,
        "CardType": "image-supported", "CardID": "heart-1",
        "ImageURL": image.name, "ImageAlt": "heart diagram",
    }])

    notes, media = load_notes(path, "Deck")

    assert notes[0].model == BASIC_MODEL
    assert notes[0].fields["Back"] == back_html
    assert notes[0].fields["CardType"] == "image-supported"
    assert notes[0].fields["ImageURL"] == "diagram.png"
    assert notes[0].fields["ImageAlt"] == "heart diagram"
    assert media == [image]


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
