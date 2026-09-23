"""Tests for the AnkiConnect client (mnemo/anki/connect.py).

Network calls are stubbed with the `responses` library -- no live Anki
instance needed. Ported/trimmed from the pre-rewrite pipeline's proven,
defensively-checked design (deck-pinning order verification, malformed-
response detection); AnkiNote/adapter concept replaced by
note_types.render_fields.
"""

import json

import pytest
import responses

from mnemo.anki.connect import AddResult, AnkiConnect, AnkiConnectError
from mnemo.anki.note_types import (
    MONO_BASIC, MONO_CLOZE, MONO_NOTE_TYPES, MONO_OVERLAPPING, MONO_TYPE,
)

URL = "http://localhost:8765"


def _ok(result):
    return {"result": result, "error": None}


def test_rejects_non_local_url():
    with pytest.raises(AnkiConnectError, match="localhost"):
        AnkiConnect(url="https://example.com")


@responses.activate
def test_is_available_true_when_version_responds():
    responses.add(responses.POST, URL, json=_ok(6))
    assert AnkiConnect(url=URL).is_available() is True


@responses.activate
def test_is_available_false_on_connection_error():
    import requests

    responses.add(responses.POST, URL, body=requests.exceptions.ConnectionError("refused"))
    assert AnkiConnect(url=URL).is_available() is False


@responses.activate
def test_invoke_raises_on_error_field():
    responses.add(responses.POST, URL, json={"result": None, "error": "deck not found"})
    with pytest.raises(AnkiConnectError, match="deck not found"):
        AnkiConnect(url=URL).deck_names()


@responses.activate
def test_invoke_raises_on_malformed_response():
    responses.add(responses.POST, URL, json={"unexpected": "shape"})
    with pytest.raises(AnkiConnectError, match="malformed"):
        AnkiConnect(url=URL).deck_names()


@responses.activate
def test_ensure_deck_creates_when_missing():
    responses.add(responses.POST, URL, json=_ok([]))
    responses.add(responses.POST, URL, json=_ok(1))
    AnkiConnect(url=URL).ensure_deck("Biology")
    assert len(responses.calls) == 2


@responses.activate
def test_ensure_deck_skips_creation_when_present():
    responses.add(responses.POST, URL, json=_ok(["Biology"]))
    AnkiConnect(url=URL).ensure_deck("Biology")
    assert len(responses.calls) == 1


@responses.activate
def test_ensure_note_types_creates_missing_model():
    responses.add(responses.POST, URL, json=_ok([]))  # modelNames
    responses.add(responses.POST, URL, json=_ok(None))  # createModel
    created = AnkiConnect(url=URL).ensure_note_types([MONO_BASIC])
    assert created == ["MONO Basic"]


@pytest.mark.parametrize(
    ("note_type", "old_fields", "added_fields"),
    [
        (MONO_BASIC, ("Front", "Back", "Source", "CardID", "RevisionHash"), ("Extra", "Mnemonic")),
        (MONO_CLOZE, ("Text", "Extra", "Source", "CardID", "RevisionHash"), ("Mnemonic",)),
        (MONO_TYPE, ("Prompt", "Answer", "Extra", "Source", "CardID", "RevisionHash"), ("Mnemonic",)),
        (MONO_OVERLAPPING, ("Title", "Text", "Source", "CardID", "RevisionHash"), ("Extra", "Mnemonic")),
    ],
)
@responses.activate
def test_ensure_note_types_appends_exact_migration_fields_before_templates(
    note_type, old_fields, added_fields,
):
    responses.add(responses.POST, URL, json=_ok([note_type.name]))
    responses.add(responses.POST, URL, json=_ok(list(old_fields)))
    for _ in added_fields:
        responses.add(responses.POST, URL, json=_ok(None))
    responses.add(responses.POST, URL, json=_ok(None))
    responses.add(responses.POST, URL, json=_ok(None))

    created = AnkiConnect(url=URL).ensure_note_types([note_type])

    assert created == []
    sent = [json.loads(call.request.body) for call in responses.calls]
    assert [request["action"] for request in sent] == [
        "modelNames", "modelFieldNames",
        *("modelFieldAdd" for _ in added_fields),
        "updateModelTemplates", "updateModelStyling",
    ]
    assert [request["params"] for request in sent[2:2 + len(added_fields)]] == [
        {"modelName": note_type.name, "fieldName": field_name}
        for field_name in added_fields
    ]


@responses.activate
def test_ensure_note_types_rejects_incompatible_existing_field_order():
    responses.add(responses.POST, URL, json=_ok(["MONO Basic"]))
    responses.add(responses.POST, URL, json=_ok(["Back", "Front"]))  # reordered
    with pytest.raises(AnkiConnectError, match="incompatible"):
        AnkiConnect(url=URL).ensure_note_types([MONO_BASIC])


@responses.activate
def test_add_notes_reports_added_and_skipped():
    responses.add(responses.POST, URL, json=_ok([111, None]))  # addNotes
    responses.add(
        responses.POST, URL,
        json=_ok([{"noteId": 111, "cards": [1, 2]}]),  # notesInfo
    )
    responses.add(responses.POST, URL, json=_ok(None))  # changeDeck

    fields = [
        {"Front": "Q1", "Back": "A1"},
        {"Front": "Q2", "Back": "A2"},
    ]
    result = AnkiConnect(url=URL).add_notes(
        deck="Biology", model="MONO Basic", fields_list=fields,
        tags_list=[["bio"], ["bio"]],
    )
    assert isinstance(result, AddResult)
    assert result.added == [111]
    assert result.skipped == 1


def test_add_notes_rejects_mismatched_fields_and_tags_lengths():
    with pytest.raises(AnkiConnectError, match="fields_list"):
        AnkiConnect(url=URL).add_notes(
            deck="Biology", model="MONO Basic",
            fields_list=[{"Front": "Q1", "Back": "A1"}, {"Front": "Q2", "Back": "A2"}],
            tags_list=[[]],
        )


@responses.activate
def test_ensure_note_types_handles_new_and_migrating_models_together():
    from mnemo.anki.note_types import MONO_CLOZE

    responses.add(responses.POST, URL, json=_ok(["MONO Basic"]))  # modelNames
    responses.add(responses.POST, URL, json=_ok(list(MONO_BASIC.fields[:-1])))  # modelFieldNames
    responses.add(responses.POST, URL, json=_ok(None))  # modelFieldAdd
    responses.add(responses.POST, URL, json=_ok(None))  # updateModelTemplates
    responses.add(responses.POST, URL, json=_ok(None))  # updateModelStyling
    responses.add(responses.POST, URL, json=_ok(None))  # createModel for MONO Cloze

    created = AnkiConnect(url=URL).ensure_note_types([MONO_BASIC, MONO_CLOZE])
    assert created == ["MONO Cloze"]


@responses.activate
def test_pin_deck_raises_on_notes_info_order_mismatch():
    responses.add(responses.POST, URL, json=_ok([111]))  # addNotes
    responses.add(responses.POST, URL, json=_ok([{"noteId": 999, "cards": [1]}]))  # wrong id

    with pytest.raises(AnkiConnectError, match="order mismatch"):
        AnkiConnect(url=URL).add_notes(
            deck="Biology", model="MONO Basic",
            fields_list=[{"Front": "Q1", "Back": "A1"}], tags_list=[[]],
        )


@responses.activate
def test_store_media_file_stores_when_no_existing_file(tmp_path):
    path = tmp_path / "img.png"
    path.write_bytes(b"fresh-bytes")

    responses.add(responses.POST, URL, json=_ok(False))  # retrieveMediaFile: not found
    responses.add(responses.POST, URL, json=_ok("img.png"))  # storeMediaFile

    name = AnkiConnect(url=URL).store_media_file(path)
    assert name == "img.png"
    assert len(responses.calls) == 2


@responses.activate
def test_add_notes_sends_exact_payload_shape():
    responses.add(responses.POST, URL, json=_ok([111]))
    responses.add(responses.POST, URL, json=_ok([{"noteId": 111, "cards": [1]}]))
    responses.add(responses.POST, URL, json=_ok(None))

    AnkiConnect(url=URL).add_notes(
        deck="Biology", model="MONO Basic",
        fields_list=[{"Front": "Q1", "Back": "A1"}], tags_list=[["bio"]],
    )
    import json

    body = json.loads(responses.calls[0].request.body)
    assert body["action"] == "addNotes"
    note = body["params"]["notes"][0]
    assert note["deckName"] == "Biology"
    assert note["modelName"] == "MONO Basic"
    assert note["fields"] == {"Front": "Q1", "Back": "A1"}
    assert note["tags"] == ["bio"]
    assert note["options"] == {"allowDuplicate": False}


@responses.activate
def test_add_notes_raises_on_result_length_mismatch():
    responses.add(responses.POST, URL, json=_ok([111]))  # only one id for two notes
    with pytest.raises(AnkiConnectError, match="result"):
        AnkiConnect(url=URL).add_notes(
            deck="Biology", model="MONO Basic",
            fields_list=[{"Front": "Q1", "Back": "A1"}, {"Front": "Q2", "Back": "A2"}],
            tags_list=[[], []],
        )


@responses.activate
def test_find_note_id_by_card_id_resolves_exact_match_without_writing():
    responses.add(responses.POST, URL, json=_ok([101]))
    responses.add(responses.POST, URL, json=_ok([{
        "noteId": 101, "modelName": "MONO Basic",
        "fields": {"CardID": {"value": "w1m1-001", "order": 3}},
    }]))

    note_id = AnkiConnect(url=URL).find_note_id_by_card_id("w1m1-001", "MONO Basic")

    assert note_id == 101
    assert [json.loads(call.request.body)["action"] for call in responses.calls] == [
        "findNotes", "notesInfo",
    ]


@responses.activate
def test_update_note_by_card_id_updates_exact_model_match():
    responses.add(responses.POST, URL, json=_ok([101]))
    responses.add(responses.POST, URL, json=_ok([{
        "noteId": 101, "modelName": "MONO Basic",
        "fields": {"CardID": {"value": "w1m1-001", "order": 3}},
    }]))
    responses.add(responses.POST, URL, json=_ok(None))

    updated = AnkiConnect(url=URL).update_note_by_card_id(
        card_id="w1m1-001", model="MONO Basic", fields={"Back": "Answer"},
    )

    assert updated is True
    assert [json.loads(call.request.body)["action"] for call in responses.calls] == [
        "findNotes", "notesInfo", "updateNoteFields",
    ]
    assert json.loads(responses.calls[0].request.body)["params"] == {
        "query": 'CardID:"w1m1-001"',
    }
    assert json.loads(responses.calls[1].request.body)["params"] == {"notes": [101]}
    assert json.loads(responses.calls[2].request.body)["params"] == {
        "note": {"id": 101, "fields": {"Back": "Answer"}},
    }


@responses.activate
def test_update_note_by_card_id_returns_false_when_no_note_matches():
    responses.add(responses.POST, URL, json=_ok([]))

    updated = AnkiConnect(url=URL).update_note_by_card_id("w1m1-001", "MONO Basic", {})

    assert updated is False
    assert len(responses.calls) == 1


@responses.activate
def test_update_note_by_card_id_rejects_multiple_matches():
    responses.add(responses.POST, URL, json=_ok([101, 102]))
    for note_id in (101, 102):
        responses.add(responses.POST, URL, json=_ok([{
            "noteId": note_id, "modelName": "MONO Basic",
            "fields": {"CardID": {"value": "w1m1-001", "order": 3}},
        }]))

    with pytest.raises(AnkiConnectError, match="multiple notes"):
        AnkiConnect(url=URL).update_note_by_card_id("w1m1-001", "MONO Basic", {})

    assert len(responses.calls) == 3


@responses.activate
def test_update_note_by_card_id_rejects_different_model():
    responses.add(responses.POST, URL, json=_ok([101]))
    responses.add(responses.POST, URL, json=_ok([{
        "noteId": 101, "modelName": "MONO Cloze",
        "fields": {"CardID": {"value": "w1m1-001", "order": 3}},
    }]))

    with pytest.raises(AnkiConnectError, match="belongs to 'MONO Cloze', expected 'MONO Basic'"):
        AnkiConnect(url=URL).update_note_by_card_id("w1m1-001", "MONO Basic", {})

    assert len(responses.calls) == 2


@responses.activate
def test_update_note_by_card_id_ignores_single_partial_match():
    responses.add(responses.POST, URL, json=_ok([101]))
    responses.add(responses.POST, URL, json=_ok([{
        "noteId": 101, "modelName": "MONO Basic",
        "fields": {"CardID": {"value": "w1m1-001-extra", "order": 3}},
    }]))

    updated = AnkiConnect(url=URL).update_note_by_card_id(
        "w1m1-001", "MONO Basic", {"Back": "Answer"},
    )

    assert updated is False
    assert len(responses.calls) == 2


@pytest.mark.parametrize(
    ("card_id", "query"),
    [
        ("with_under", r'CardID:"with\_under"'),
        ("with*star", r'CardID:"with\*star"'),
        ('with"quote', r'CardID:"with\"quote"'),
        (r"with\slash", r'CardID:"with\\slash"'),
        ("with&ampersand", 'CardID:"with&amp;ampersand"'),
        ("with<angle>", 'CardID:"with&lt;angle&gt;"'),
    ],
)
@responses.activate
def test_find_note_by_card_id_escapes_anki_search_syntax(card_id, query):
    responses.add(responses.POST, URL, json=_ok([]))

    assert AnkiConnect(url=URL).find_note_id_by_card_id(card_id, "MONO Basic") is None
    assert json.loads(responses.calls[0].request.body)["params"]["query"] == query


@responses.activate
def test_find_note_by_card_id_filters_case_distinct_and_partial_candidates():
    responses.add(responses.POST, URL, json=_ok([101, 102, 103]))
    for note_id, value in ((101, "ALPHA"), (102, "alpha-suffix"), (103, "alpha")):
        responses.add(responses.POST, URL, json=_ok([{
            "noteId": note_id, "modelName": "MONO Basic",
            "fields": {"CardID": {"value": value, "order": 3}},
        }]))

    note_id = AnkiConnect(url=URL).find_note_id_by_card_id("alpha", "MONO Basic")

    assert note_id == 103
    assert len(responses.calls) == 4


@pytest.mark.parametrize("lookup_result", [None, {}, ["101"], [True]])
@responses.activate
def test_update_note_by_card_id_rejects_malformed_lookup_result(lookup_result):
    responses.add(responses.POST, URL, json=_ok(lookup_result))

    with pytest.raises(AnkiConnectError, match="invalid CardID match result"):
        AnkiConnect(url=URL).update_note_by_card_id("w1m1-001", "MONO Basic", {})

    assert len(responses.calls) == 1


@pytest.mark.parametrize(
    "info_result",
    [None, [], [{"noteId": 101, "modelName": "MONO Basic"}] * 2,
     [{"noteId": 102, "modelName": "MONO Basic"}],
     [{"noteId": 101}], [{"noteId": 101, "modelName": ""}],
     [{"noteId": 101, "modelName": 123}],
     [{"noteId": 101, "modelName": "MONO Basic", "fields": {}}],
     [{"noteId": 101, "modelName": "MONO Basic", "fields": {"CardID": "w1m1-001"}}]],
)
@responses.activate
def test_update_note_by_card_id_rejects_malformed_note_info(info_result):
    responses.add(responses.POST, URL, json=_ok([101]))
    responses.add(responses.POST, URL, json=_ok(info_result))

    with pytest.raises(AnkiConnectError, match="notesInfo"):
        AnkiConnect(url=URL).update_note_by_card_id("w1m1-001", "MONO Basic", {})

    assert len(responses.calls) == 2


@responses.activate
def test_store_media_file_skips_reupload_of_identical_content(tmp_path):
    import base64

    path = tmp_path / "img.png"
    path.write_bytes(b"fake-image-bytes")
    encoded = base64.b64encode(b"fake-image-bytes").decode("ascii")

    responses.add(responses.POST, URL, json=_ok(encoded))  # retrieveMediaFile
    name = AnkiConnect(url=URL).store_media_file(path)
    assert name == "img.png"
    assert len(responses.calls) == 1  # no storeMediaFile call needed


@responses.activate
def test_store_media_file_rejects_overwriting_different_content(tmp_path):
    import base64

    path = tmp_path / "img.png"
    path.write_bytes(b"new-bytes")
    different = base64.b64encode(b"old-bytes").decode("ascii")

    responses.add(responses.POST, URL, json=_ok(different))
    with pytest.raises(AnkiConnectError, match="different file"):
        AnkiConnect(url=URL).store_media_file(path)


@responses.activate
def test_sync_invokes_sync_action():
    responses.add(responses.POST, URL, json=_ok(None))
    AnkiConnect(url=URL).sync()
    assert b'"action": "sync"' in responses.calls[0].request.body or \
           b'"action":"sync"' in responses.calls[0].request.body
