"""Tests for the AnkiConnect backend (scripts/anki_connect.py).

Uses the `responses` library to mock the localhost AnkiConnect HTTP API, so no
live Anki is required. AnkiConnect exposes a single endpoint; the action is in
the POSTed JSON body, so we dispatch the mock by action name.
"""

import json
import base64

import pytest
import requests
import responses

from scripts.adapter import AnkiNote
from scripts.anki_connect import AnkiConnect, AnkiConnectError

URL = "http://localhost:8765"


def _dispatch(results_by_action):
    """Return a responses callback that routes by the request's 'action'."""
    def callback(request):
        payload = json.loads(request.body)
        action = payload["action"]
        if action not in results_by_action:
            return (200, {}, json.dumps({"result": None, "error": f"no mock for {action}"}))
        result = results_by_action[action]
        if callable(result):
            result = result(payload)
        return (200, {}, json.dumps({"result": result, "error": None}))
    return callback


def _register(results_by_action):
    responses.add_callback(
        responses.POST, URL, callback=_dispatch(results_by_action),
        content_type="application/json",
    )


@responses.activate
def test_invoke_returns_result():
    _register({"deckNames": ["Default", "Geography"]})
    client = AnkiConnect(URL)
    assert client.deck_names() == ["Default", "Geography"]


@responses.activate
def test_invoke_raises_on_error_field():
    _register({"createDeck": lambda p: None})  # fine
    # Override with an explicit error response:
    responses.reset()
    responses.add(responses.POST, URL,
                  json={"result": None, "error": "deck exists"}, status=200)
    client = AnkiConnect(URL)
    with pytest.raises(AnkiConnectError, match="deck exists"):
        client.create_deck("X")


@responses.activate
def test_is_available_true_when_version_responds():
    _register({"version": 6})
    assert AnkiConnect(URL).is_available() is True


def test_is_available_false_on_connection_error():
    # No responses registered + not activated -> connection fails.
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.POST, URL, body=requests.ConnectionError("down"))
        assert AnkiConnect(URL).is_available() is False


@responses.activate
def test_ensure_deck_creates_only_when_missing():
    created = []
    _register({
        "deckNames": ["Default"],
        "createDeck": lambda p: created.append(p["params"]["deck"]) or 12345,
    })
    client = AnkiConnect(URL)
    client.ensure_deck("Geography")   # missing -> create
    client.ensure_deck("Default")     # present -> no create
    assert created == ["Geography"]


@responses.activate
def test_add_notes_counts_added_and_skipped():
    sent = {}
    def add_notes(payload):
        sent["notes"] = payload["params"]["notes"]
        # Second note is a duplicate -> AnkiConnect returns null for it.
        return [1001, None]
    _register({
        "addNotes": add_notes,
        "notesInfo": lambda p: [{"cards": [5001]}],
        "changeDeck": lambda p: None,
    })

    notes = [
        AnkiNote(model="MONO Basic", deck="Geo",
                 fields={"Front": "Q", "Back": "A"}, tags=["geo"]),
        AnkiNote(model="MONO Basic", deck="Geo",
                 fields={"Front": "Q", "Back": "A"}, tags=["geo"]),
    ]
    result = AnkiConnect(URL).add_notes(notes)
    assert result.added == [1001]
    assert result.skipped == 1
    # Payload shape sanity:
    first = sent["notes"][0]
    assert first["deckName"] == "Geo"
    assert first["modelName"] == "MONO Basic"
    assert first["fields"]["Front"] == "Q"
    assert first["options"]["allowDuplicate"] is False


@responses.activate
def test_add_notes_pins_new_cards_to_their_target_decks():
    # Regression: some Anki/AnkiConnect builds ignore addNotes' deckName and dump
    # every card into Default. add_notes must re-home each new card via changeDeck.
    changed = []
    def notes_info(payload):
        # AnkiConnect returns card ids per requested note, in order.
        return [{"cards": [7001]}, {"cards": [7002, 7003]}]
    def change_deck(payload):
        changed.append((tuple(payload["params"]["cards"]), payload["params"]["deck"]))
        return None
    _register({
        "addNotes": lambda p: [9001, 9002],
        "notesInfo": notes_info,
        "changeDeck": change_deck,
    })

    notes = [
        AnkiNote(model="MONO Basic", deck="Geography",
                 fields={"Front": "Q", "Back": "A"}, tags=[]),
        AnkiNote(model="MONO Cloze", deck="Chemistry::Basics",
                 fields={"Text": "{{c1::x}}"}, tags=[]),
    ]
    result = AnkiConnect(URL).add_notes(notes)

    assert result.added == [9001, 9002]
    # Each note's cards land in that note's deck (grouped per deck).
    assert ((7001,), "Geography") in changed
    assert ((7002, 7003), "Chemistry::Basics") in changed


@responses.activate
def test_change_deck_noop_on_empty_card_list():
    # No HTTP call should be made for an empty card set.
    _register({"changeDeck": lambda p: pytest.fail("changeDeck called with no cards")})
    AnkiConnect(URL).change_deck([], "Geography")


@responses.activate
def test_ensure_note_types_creates_missing_models_with_cloze_flag():
    from scripts.note_types import MONO_NOTE_TYPES
    created = []
    updated_templates = []
    updated_styling = []
    _register({
        "modelNames": ["MONO Basic"],  # Other bundled models are missing.
        "createModel": lambda p: created.append(p["params"]) or {"id": 1},
        "updateModelTemplates": lambda p: updated_templates.append(p["params"]),
        "updateModelStyling": lambda p: updated_styling.append(p["params"]),
    })
    AnkiConnect(URL).ensure_note_types(MONO_NOTE_TYPES.values())
    names = {c["modelName"] for c in created}
    assert names == {"MONO Cloze", "MONO Overlapping", "MONO Type"}
    cloze_payload = next(c for c in created if c["modelName"] == "MONO Cloze")
    assert cloze_payload["isCloze"] is True
    assert "Text" in cloze_payload["inOrderFields"]
    assert updated_templates[0]["model"]["name"] == "MONO Basic"
    assert "Card 1" in updated_templates[0]["model"]["templates"]
    assert updated_styling[0]["model"]["name"] == "MONO Basic"
    assert "_outfit-variable.ttf" in updated_styling[0]["model"]["css"]


@responses.activate
def test_ensure_models_exist_reports_missing_external_type():
    _register({"modelNames": ["Basic", "MONO Basic"]})
    client = AnkiConnect(URL)
    with pytest.raises(AnkiConnectError, match="Image Occlusion"):
        client.ensure_models_exist(["Basic", "Image Occlusion"])


@responses.activate
def test_store_media_file_sends_base64(tmp_path):
    media = tmp_path / "diagram.png"
    media.write_bytes(b"png bytes")
    sent = {}

    def store(payload):
        sent.update(payload["params"])
        return payload["params"]["filename"]

    _register({"storeMediaFile": store})
    result = AnkiConnect(URL).store_media_file(media)

    assert result == "diagram.png"
    assert sent["data"] == base64.b64encode(b"png bytes").decode("ascii")
