"""Tests for the mnemo CLI (mnemo/cli.py).

Tests call the cmd_* functions directly (the logic argparse dispatches to)
rather than shelling out -- faster and lets us assert on return values, not
just stdout. AnkiConnect calls are stubbed with `responses`.
"""

import json

import pytest
import responses

from mnemo.card import Card
from mnemo.cli import build_parser, cmd_audit, cmd_draft, cmd_export_note_types, cmd_import, main
from mnemo.deck import Deck, read_deck, write_deck

URL = "http://localhost:8765"


def _ok(result):
    return {"result": result, "error": None}


def write_test_deck(tmp_path, name="Biology", *, cards=None, tags=None):
    path = tmp_path / "biology.mnemo.yaml"
    write_deck(path, Deck(
        name=name,
        cards=cards if cards is not None else [
            Card(front="What is ATP?", back="Adenosine triphosphate.", card_id="atp")
        ],
        tags=tags if tags is not None else [],
    ))
    return path


def test_build_parser_has_all_five_subcommands():
    parser = build_parser()
    subcommand_dest = [a for a in parser._subparsers._group_actions if a.dest == "command"][0]
    assert set(subcommand_dest.choices) == {
        "ingest", "draft", "audit", "import", "export-note-types",
    }


def test_cmd_draft_writes_cards_and_deferred(tmp_path, capsys):
    source = tmp_path / "notes.md"
    source.write_text(
        "Q: What is ATP?\nA: Adenosine triphosphate.\n\n"
        "Some prose that cannot be grounded confidently at all.\n"
    )
    cards_out = tmp_path / "biology.mnemo.yaml"
    deferred_out = tmp_path / "deferred.md"

    exit_code = cmd_draft(source, cards_out, deferred_out, deck="Biology")

    assert exit_code == 0
    deck = read_deck(cards_out)
    assert deck.name == "Biology"
    assert len(deck.cards) == 1
    assert deck.cards[0].front == "What is ATP?"
    assert deck.cards[0].card_id
    assert deferred_out.exists()
    assert "no confident grounding" in deferred_out.read_text()


def test_cmd_audit_returns_zero_on_pass(tmp_path):
    path = write_test_deck(tmp_path, cards=[Card(
        front="What is ATP?", back="Adenosine triphosphate.", card_id="atp",
        extra="Explanation: it stores energy.", source="notes.md",
    )])
    assert cmd_audit(path) == 0


def test_cmd_audit_returns_one_on_fail(tmp_path):
    path = write_test_deck(tmp_path, cards=[Card(
        front="No deletion here.", back="x", card_type="cloze", card_id="bad-cloze",
    )])
    assert cmd_audit(path) == 1


def _dispatching_ankiconnect_callback(request):
    """Return a plausible result for every action mnemo's import path can
    send, dispatched by action name rather than call order -- robust against
    ensure_note_types iterating an arbitrary number of note types."""
    import json as _json

    from mnemo.anki.note_types import MONO_NOTE_TYPES

    body = _json.loads(request.body)
    action = body["action"]
    params = body.get("params", {})

    if action == "version":
        result = 6
    elif action == "deckNames":
        result = ["Biology"]
    elif action == "modelNames":
        result = list(MONO_NOTE_TYPES)
    elif action == "modelFieldNames":
        result = list(MONO_NOTE_TYPES[params["modelName"]].fields)
    elif action == "addNotes":
        result = [111] * len(params.get("notes", []))
    elif action == "notesInfo":
        result = [{"noteId": nid, "cards": [nid]} for nid in params.get("notes", [])]
    elif action in {
        "updateModelTemplates", "updateModelStyling", "createModel",
        "modelFieldAdd", "changeDeck", "sync",
    }:
        result = None
    elif action == "createDeck":
        result = 1
    else:
        raise AssertionError(f"unexpected AnkiConnect action in test: {action!r}")

    return (200, {}, _json.dumps({"result": result, "error": None}))


@responses.activate
def test_cmd_import_uses_ankiconnect_when_available(tmp_path):
    path = write_test_deck(tmp_path, name="Mnemo::Biology", tags=["science"])

    responses.add_callback(responses.POST, URL, callback=_dispatching_ankiconnect_callback)

    exit_code = cmd_import(path, config_path=None, apkg_out=None)
    assert exit_code == 0
    requests_sent = [json.loads(call.request.body) for call in responses.calls]
    assert any(req["action"] == "createDeck" and req["params"]["deck"] == "Mnemo::Biology"
               for req in requests_sent)
    added = next(req for req in requests_sent if req["action"] == "addNotes")
    assert added["params"]["notes"][0]["deckName"] == "Mnemo::Biology"
    assert added["params"]["notes"][0]["tags"] == ["science"]


@responses.activate
def test_cmd_import_falls_back_to_apkg_when_ankiconnect_unavailable(tmp_path):
    from contextlib import closing
    import requests
    import sqlite3
    import zipfile

    path = write_test_deck(tmp_path, name="Mnemo::Biology", tags=["science"])
    apkg_out = tmp_path / "deck.apkg"

    responses.add(responses.POST, URL, body=requests.exceptions.ConnectionError("refused"))

    exit_code = cmd_import(path, config_path=None, apkg_out=apkg_out)

    assert exit_code == 0
    assert apkg_out.exists()
    with zipfile.ZipFile(apkg_out) as archive:
        collection_path = tmp_path / "collection.anki2"
        collection_path.write_bytes(archive.read("collection.anki2"))
    with closing(sqlite3.connect(collection_path)) as connection:
        decks = json.loads(connection.execute("SELECT decks FROM col").fetchone()[0])
        card_deck_id = connection.execute("SELECT did FROM cards").fetchone()[0]
        note_tags = connection.execute("SELECT tags FROM notes").fetchone()[0]
    assert decks[str(card_deck_id)]["name"] == "Mnemo::Biology"
    assert "science" in note_tags.split()


@responses.activate
def test_cmd_export_note_types_creates_all_mono_types():
    responses.add(responses.POST, URL, json=_ok(6))  # is_available via version
    responses.add(responses.POST, URL, json=_ok([]))  # modelNames
    for _ in range(4):
        responses.add(responses.POST, URL, json=_ok(None))  # createModel x4

    exit_code = cmd_export_note_types(config_path=None)
    assert exit_code == 0


def test_main_dispatches_to_audit(tmp_path):
    path = write_test_deck(tmp_path)
    assert main(["audit", str(path)]) == 0


def test_cmd_ingest_prints_chunks(tmp_path, capsys):
    from mnemo.cli import cmd_ingest

    source = tmp_path / "notes.md"
    source.write_text("Mitochondria produce ATP.")

    exit_code = cmd_ingest(source)

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "notes.md" in out
    assert "Mitochondria produce ATP." in out


def test_main_dispatches_to_ingest(tmp_path, capsys):
    source = tmp_path / "notes.md"
    source.write_text("Mitochondria produce ATP.")

    assert main(["ingest", str(source)]) == 0
    assert "Mitochondria" in capsys.readouterr().out


def test_main_dispatches_to_draft(tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("Q: What is ATP?\nA: Adenosine triphosphate.\n")
    cards_out = tmp_path / "biology.mnemo.yaml"

    assert main(["draft", str(source), "--deck", "Biology", "-o", str(cards_out)]) == 0
    assert cards_out.exists()


def test_draft_both_directions_produces_unique_stable_ids(tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("Wika: A language system.\n")
    output = tmp_path / "wika.mnemo.yaml"

    assert main(["draft", str(source), "--deck", "Mnemo::Wika", "--directions", "both",
                 "-o", str(output)]) == 0
    first = read_deck(output)
    assert first.name == "Mnemo::Wika"
    assert [card.front for card in first.cards] == [
        "What is wika?", "What is the term for A language system?",
    ]
    assert len({card.card_id for card in first.cards}) == 2

    assert main(["draft", str(source), "--deck", "Mnemo::Wika", "--directions", "both",
                 "-o", str(output)]) == 0
    assert [card.card_id for card in read_deck(output).cards] == [
        card.card_id for card in first.cards
    ]


def test_draft_requires_deck_name(tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("Q: What is ATP?\nA: Adenosine triphosphate.\n")
    with pytest.raises(SystemExit):
        main(["draft", str(source), "-o", str(tmp_path / "biology.mnemo.yaml")])


def test_import_rejects_removed_deck_option():
    with pytest.raises(SystemExit):
        main(["import", "biology.mnemo.yaml", "--deck", "Biology"])


@pytest.mark.parametrize("command", ["audit", "import"])
def test_yaml_only_commands_reject_csv_paths(command, tmp_path, capsys):
    path = tmp_path / "cards.csv"
    path.write_text("front,back\nWhat is ATP?,Adenosine triphosphate.\n")

    assert main([command, str(path)]) == 1
    assert "deck manifest" in capsys.readouterr().err


def test_draft_ocr_and_lang_flags_are_threaded_through_to_ingest(tmp_path, monkeypatch):
    import mnemo.cli as cli_module

    source = tmp_path / "notes.pdf"
    source.write_text("not a real pdf, ingest() is stubbed below")
    cards_out = tmp_path / "biology.mnemo.yaml"
    seen = {}

    def fake_ingest(path, *, ocr=False, extract_images=None, language="eng", **kwargs):
        seen["ocr"] = ocr
        seen["language"] = language
        return []

    monkeypatch.setattr(cli_module, "ingest", fake_ingest)

    exit_code = main(["draft", str(source), "--deck", "Biology", "-o", str(cards_out),
                      "--ocr", "--lang", "fil"])

    assert exit_code == 0
    assert seen["ocr"] is True
    assert seen["language"] == "fil"


def test_ingest_lang_flag_defaults_to_english(tmp_path, monkeypatch):
    import mnemo.cli as cli_module

    source = tmp_path / "notes.pdf"
    source.write_text("not a real pdf, ingest() is stubbed below")
    seen = {}

    def fake_ingest(path, *, ocr=False, extract_images=None, language="eng", **kwargs):
        seen["language"] = language
        return []

    monkeypatch.setattr(cli_module, "ingest", fake_ingest)

    main(["ingest", str(source)])

    assert seen["language"] == "eng"


def test_ingest_pages_and_prose_lang_flags_are_parsed_and_threaded(tmp_path, monkeypatch):
    import mnemo.cli as cli_module

    source = tmp_path / "notes.pdf"
    source.write_text("not a real pdf, ingest() is stubbed below")
    seen = {}

    def fake_ingest(path, *, ocr=False, extract_images=None, language="eng",
                     pages=None, prose_language=None):
        seen["pages"] = pages
        seen["prose_language"] = prose_language
        return []

    monkeypatch.setattr(cli_module, "ingest", fake_ingest)

    main(["ingest", str(source), "--pages", "1-30", "--prose-lang", "fil"])

    assert seen == {"pages": (1, 30), "prose_language": "fil"}


def test_draft_pages_and_prose_lang_flags_are_parsed_and_threaded(tmp_path, monkeypatch):
    import mnemo.cli as cli_module

    source = tmp_path / "notes.pdf"
    source.write_text("not a real pdf, ingest() is stubbed below")
    cards_out = tmp_path / "biology.mnemo.yaml"
    seen = {}

    def fake_ingest(path, *, ocr=False, extract_images=None, language="eng",
                     pages=None, prose_language=None):
        seen["pages"] = pages
        seen["prose_language"] = prose_language
        return []

    monkeypatch.setattr(cli_module, "ingest", fake_ingest)

    main(["draft", str(source), "--deck", "Biology", "-o", str(cards_out),
          "--pages", "1-10", "--prose-lang", "eng"])

    assert seen == {"pages": (1, 10), "prose_language": "eng"}


def test_invalid_page_range_is_a_clean_argparse_error(capsys):
    with pytest.raises(SystemExit):
        main(["ingest", "notes.pdf", "--pages", "not-a-range"])
    assert "invalid page range" in capsys.readouterr().err


def test_page_range_end_before_start_is_rejected(capsys):
    with pytest.raises(SystemExit):
        main(["ingest", "notes.pdf", "--pages", "10-5"])
    assert "invalid page range" in capsys.readouterr().err


@responses.activate
def test_main_dispatches_to_import(tmp_path):
    path = write_test_deck(tmp_path)
    responses.add_callback(responses.POST, URL, callback=_dispatching_ankiconnect_callback)

    assert main(["import", str(path)]) == 0


@responses.activate
def test_main_dispatches_to_export_note_types():
    responses.add_callback(responses.POST, URL, callback=_dispatching_ankiconnect_callback)
    assert main(["export-note-types"]) == 0


@responses.activate
def test_cmd_export_note_types_returns_error_when_unavailable():
    import requests

    responses.add(responses.POST, URL, body=requests.exceptions.ConnectionError("refused"))
    assert cmd_export_note_types(config_path=None) == 1


def test_main_reports_clean_error_on_missing_source_file(tmp_path, capsys):
    missing = tmp_path / "absent.md"
    exit_code = main(["ingest", str(missing)])
    assert exit_code == 1
    assert "File not found" in capsys.readouterr().err


def test_cmd_draft_default_deferred_path_is_named_after_cards_out(tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("Some unstructured prose that cannot ground confidently.\n")
    cards_out = tmp_path / "module1.mnemo.yaml"

    cmd_draft(source, cards_out, deck="Biology")

    assert (tmp_path / "module1.mnemo.deferred.md").exists()
    assert not (tmp_path / "deferred.md").exists()


@responses.activate
def test_cmd_import_reports_clean_error_when_ankiconnect_fails_mid_import(tmp_path, capsys):
    path = write_test_deck(tmp_path)

    def flaky_callback(request):
        import json as _json

        body = _json.loads(request.body)
        if body["action"] == "version":
            return (200, {}, _json.dumps({"result": 6, "error": None}))
        return (200, {}, _json.dumps({"result": None, "error": "collection is locked"}))

    responses.add_callback(responses.POST, URL, callback=flaky_callback)

    exit_code = main(["import", str(path)])

    assert exit_code == 1
    assert "collection is locked" in capsys.readouterr().err


@responses.activate
def test_cmd_import_reports_which_cards_were_skipped(tmp_path, capsys):
    path = write_test_deck(tmp_path, cards=[
        Card(front="What is ATP?", back="Adenosine triphosphate.", source="notes.md", card_id="atp"),
        Card(front="What is DNA?", back="Deoxyribonucleic acid.", source="notes.md", card_id="dna"),
    ])

    def skip_second_callback(request):
        import json as _json

        from mnemo.anki.note_types import MONO_NOTE_TYPES

        body = _json.loads(request.body)
        action = body["action"]
        params = body.get("params", {})
        if action == "version":
            result = 6
        elif action == "deckNames":
            result = ["Biology"]
        elif action == "modelNames":
            result = list(MONO_NOTE_TYPES)
        elif action == "modelFieldNames":
            result = list(MONO_NOTE_TYPES[params["modelName"]].fields)
        elif action == "addNotes":
            result = [111, None]  # second note refused (e.g. duplicate)
        elif action == "notesInfo":
            result = [{"noteId": 111, "cards": [1]}]
        elif action in {"updateModelTemplates", "updateModelStyling", "changeDeck", "sync"}:
            result = None
        else:
            raise AssertionError(f"unexpected action: {action!r}")
        return (200, {}, _json.dumps({"result": result, "error": None}))

    responses.add_callback(responses.POST, URL, callback=skip_second_callback)

    exit_code = main(["import", str(path)])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "1 skipped" in out
    skipped_lines = [line for line in out.splitlines() if "SKIPPED" in line]
    assert len(skipped_lines) == 1
    assert "What is DNA?" in skipped_lines[0]
