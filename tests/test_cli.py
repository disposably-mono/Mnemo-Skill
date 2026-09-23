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


def test_help_describes_yaml_only_deck_workflow(capsys):
    with pytest.raises(SystemExit):
        main(["draft", "--help"])
    assert ".mnemo.yaml" in capsys.readouterr().out


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
    assert "findNotes" not in [req["action"] for req in requests_sent]


def test_import_parser_accepts_update_existing_flag():
    args = build_parser().parse_args(["import", "deck.mnemo.yaml", "--update-existing"])
    assert args.update_existing is True


@responses.activate
@pytest.mark.parametrize("include_unmatched", [False, True])
def test_import_update_existing_updates_exact_match_and_adds_unmatched(
    tmp_path, capsys, include_unmatched,
):
    cards = [
        Card(front="What is ATP?", back="New answer", extra="New explanation",
             mnemonic="New memory cue", card_id="atp"),
    ]
    if include_unmatched:
        cards = [*cards, Card(front="What is DNA?", back="New DNA answer", card_id="dna")]
    path = write_test_deck(tmp_path, cards=cards)

    def callback(request):
        body = json.loads(request.body)
        if body["action"] == "updateNoteFields":
            return (200, {}, json.dumps(_ok(None)))
        if body["action"] == "findNotes":
            return (200, {}, json.dumps(_ok([900] if body["params"]["query"] == 'CardID:"atp"' else [])))
        if body["action"] == "notesInfo" and body["params"]["notes"] == [900]:
            return (200, {}, json.dumps(_ok([{
                "noteId": 900, "modelName": "MONO Basic",
                "fields": {"CardID": {"value": "atp", "order": 0}}, "cards": [901],
            }])))
        return _dispatching_ankiconnect_callback(request)

    responses.add_callback(responses.POST, URL, callback=callback)
    assert main(["import", str(path), "--update-existing"]) == 0

    sent = [json.loads(call.request.body) for call in responses.calls]
    updates = [request for request in sent if request["action"] == "updateNoteFields"]
    assert len(updates) == 1
    assert updates[0]["params"]["note"]["id"] == 900
    assert updates[0]["params"]["note"]["fields"]["Back"] == "New answer"
    assert updates[0]["params"]["note"]["fields"]["Extra"] == "New explanation"
    assert updates[0]["params"]["note"]["fields"]["Mnemonic"] == "New memory cue"
    added = [request for request in sent if request["action"] == "addNotes"]
    if include_unmatched:
        assert len(added) == 1
        assert [note["fields"]["CardID"] for note in added[0]["params"]["notes"]] == ["dna"]
    else:
        assert added == []
    expected_added = 1 if include_unmatched else 0
    assert f"{expected_added} added, 1 updated, 0 skipped" in capsys.readouterr().out


@responses.activate
def test_import_update_existing_rejects_missing_card_id_before_ankiconnect():
    from mnemo.anki.connect import AnkiConnect
    from mnemo.cli import _import_via_ankiconnect
    from mnemo.config import load_config

    cards = [
        Card(front="What is ATP?", back="Answer", card_id="atp"),
        Card(front="What is DNA?", back="Answer", card_id=None),
    ]
    responses.add_callback(responses.POST, URL, callback=_dispatching_ankiconnect_callback)

    with pytest.raises(ValueError, match="CardID"):
        _import_via_ankiconnect(cards, "Biology", load_config(None), AnkiConnect(url=URL),
                                update_existing=True)
    assert len(responses.calls) == 0


@responses.activate
def test_import_update_existing_falls_back_to_apkg_without_updating(tmp_path, capsys):
    import requests

    path = write_test_deck(tmp_path)
    output = tmp_path / "fallback.apkg"
    responses.add(responses.POST, URL, body=requests.exceptions.ConnectionError("refused"))

    assert main(["import", str(path), "--update-existing", "--apkg-out", str(output)]) == 0
    assert output.exists()
    assert "exported 1 card(s)" in capsys.readouterr().out
    assert [json.loads(call.request.body)["action"] for call in responses.calls] == ["version"]


@responses.activate
@pytest.mark.parametrize("invalid_result", [[901, 902], [901]])
@pytest.mark.parametrize("first_result", [[900], []])
def test_import_update_existing_preflights_all_targets_before_writes(
    tmp_path, capsys, invalid_result, first_result,
):
    path = write_test_deck(tmp_path, cards=[
        Card(front="First", back="Updated first", card_id="first"),
        Card(front="Second", back="Updated second", card_id="second"),
    ])

    def callback(request):
        body = json.loads(request.body)
        if body["action"] == "updateNoteFields":
            return (200, {}, json.dumps(_ok(None)))
        if body["action"] == "findNotes":
            result = first_result if body["params"]["query"] == 'CardID:"first"' else invalid_result
            return (200, {}, json.dumps(_ok(result)))
        if body["action"] == "notesInfo":
            note_id = body["params"]["notes"][0]
            model = "MONO Cloze" if note_id == 901 else "MONO Basic"
            return (200, {}, json.dumps(_ok([{
                "noteId": note_id, "modelName": model,
                "fields": {"CardID": {"value": "first" if note_id == 900 else "second"}},
            }])))
        return _dispatching_ankiconnect_callback(request)

    responses.add_callback(responses.POST, URL, callback=callback)

    assert main(["import", str(path), "--update-existing"]) == 1
    assert "CardID" in capsys.readouterr().err
    actions = [json.loads(call.request.body)["action"] for call in responses.calls]
    assert "findNotes" in actions
    assert "updateNoteFields" not in actions
    assert "addNotes" not in actions


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


def test_draft_ids_distinguish_deck_and_source_contexts(tmp_path):
    from mnemo.anki.export import _to_genanki_note
    from mnemo.anki.note_types import MONO_BASIC

    first_source = tmp_path / "first.md"
    second_source = tmp_path / "second.md"
    first_source.write_text("Q: What is ATP?\nA: Adenosine triphosphate.\n")
    second_source.write_text(first_source.read_text())
    first_path = tmp_path / "first.mnemo.yaml"
    other_deck_path = tmp_path / "other-deck.mnemo.yaml"
    other_source_path = tmp_path / "other-source.mnemo.yaml"

    assert cmd_draft(first_source, first_path, deck="Biology") == 0
    assert cmd_draft(first_source, other_deck_path, deck="Science") == 0
    assert cmd_draft(second_source, other_source_path, deck="Biology") == 0

    cards = [read_deck(path).cards[0] for path in (
        first_path, other_deck_path, other_source_path,
    )]
    assert len({card.card_id for card in cards}) == 3
    assert len({_to_genanki_note(card, MONO_BASIC).guid for card in cards}) == 3

    assert cmd_draft(first_source, first_path, deck="Biology") == 0
    repeated = read_deck(first_path).cards[0]
    assert repeated.card_id == cards[0].card_id
    assert _to_genanki_note(repeated, MONO_BASIC).guid == _to_genanki_note(cards[0], MONO_BASIC).guid


def test_draft_ids_resolve_relative_source_across_working_directories(tmp_path, monkeypatch):
    from mnemo.anki.export import _to_genanki_note
    from mnemo.anki.note_types import MONO_BASIC

    first_dir = tmp_path / "course-a"
    second_dir = tmp_path / "course-b"
    first_dir.mkdir()
    second_dir.mkdir()
    for directory in (first_dir, second_dir):
        (directory / "notes.md").write_text("Q: What is ATP?\nA: Adenosine triphosphate.\n")

    monkeypatch.chdir(first_dir)
    assert cmd_draft("notes.md", first_dir / "deck.mnemo.yaml", deck="Biology") == 0
    first_card = read_deck(first_dir / "deck.mnemo.yaml").cards[0]

    monkeypatch.chdir(second_dir)
    assert cmd_draft("notes.md", second_dir / "deck.mnemo.yaml", deck="Biology") == 0
    second_card = read_deck(second_dir / "deck.mnemo.yaml").cards[0]

    assert first_card.card_id != second_card.card_id
    assert _to_genanki_note(first_card, MONO_BASIC).guid != _to_genanki_note(second_card, MONO_BASIC).guid

    monkeypatch.chdir(first_dir)
    assert cmd_draft("notes.md", first_dir / "deck.mnemo.yaml", deck="Biology") == 0
    assert read_deck(first_dir / "deck.mnemo.yaml").cards[0].card_id == first_card.card_id


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
