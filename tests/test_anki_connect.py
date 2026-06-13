"""Tests for the AnkiConnect backend (scripts/anki_connect.py).

Uses the `responses` library to mock the localhost AnkiConnect HTTP API, so no
live Anki is required. AnkiConnect exposes a single endpoint; the action is in
the POSTed JSON body, so we dispatch the mock by action name.
"""

import json

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
    _register({"addNotes": add_notes})

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
def test_ensure_note_types_creates_missing_models_with_cloze_flag():
    from scripts.note_types import MONO_NOTE_TYPES
    created = []
    _register({
        "modelNames": ["MONO Basic"],  # Cloze + Overlapping missing
        "createModel": lambda p: created.append(p["params"]) or {"id": 1},
    })
    AnkiConnect(URL).ensure_note_types(MONO_NOTE_TYPES.values())
    names = {c["modelName"] for c in created}
    assert names == {"MONO Cloze", "MONO Overlapping"}
    cloze_payload = next(c for c in created if c["modelName"] == "MONO Cloze")
    assert cloze_payload["isCloze"] is True
    assert "Text" in cloze_payload["inOrderFields"]
