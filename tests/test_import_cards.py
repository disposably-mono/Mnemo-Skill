"""Tests for the import orchestrator (scripts/import_cards.py).

The orchestrator ties the pipeline together: load Facts from JSONL -> adapt to
notes -> push via AnkiConnect when it's reachable, else export a .apkg. We inject
a fake AnkiConnect client so no live Anki (and no real HTTP) is needed; the
.apkg fallback path writes a real package into tmp_path.
"""

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from scripts.anki_connect import AddResult
from scripts.card_schema import Fact, dump_facts
from scripts.import_cards import (
    ImportReport,
    _format_summary,
    import_cards,
    main,
)


class FakeClient:
    """Records the calls the orchestrator makes against an AnkiConnect client."""

    def __init__(self, available=True):
        self._available = available
        self.ensured_decks = []
        self.ensured_note_types = False
        self.added = []
        self.synced = False
        self.ensured_models = []
        self.stored_media = []

    def is_available(self):
        return self._available

    def ensure_note_types(self, note_types):
        self.ensured_note_types = True
        return []

    def ensure_deck(self, name):
        self.ensured_decks.append(name)

    def ensure_models_exist(self, names):
        self.ensured_models.extend(names)

    def store_media_files(self, paths):
        self.stored_media.extend(paths)
        return [path.name for path in paths]

    def add_notes(self, notes):
        self.added.extend(notes)
        # Pretend the last note is a duplicate to exercise skip counting.
        added_ids = list(range(len(notes) - 1))
        return AddResult(added=added_ids, skipped=1 if notes else 0)

    def sync(self):
        self.synced = True


def _write_facts(path):
    facts = [
        Fact.from_dict({
            "type": "qa",
            "content": {"front": "Capital of France?", "back": "Paris"},
            "deck": "Geography",
            "tags": ["geo", "auto"],
        }),
        Fact.from_dict({
            "type": "cloze",
            "content": {"text": "Water is {{c1::H2O}}."},
            "deck": "Chemistry::Basics",
            "tags": ["chem"],
        }),
    ]
    dump_facts(facts, path)
    return facts


def test_import_via_ankiconnect_when_available(tmp_path):
    jsonl = tmp_path / "session.jsonl"
    _write_facts(jsonl)
    client = FakeClient(available=True)

    report = import_cards(jsonl, client=client)

    assert isinstance(report, ImportReport)
    assert report.backend == "ankiconnect"
    assert client.ensured_note_types is True
    assert set(client.ensured_decks) == {"Geography", "Chemistry::Basics"}
    assert len(client.added) == 2
    # One AnkiNote per fact, adapted to its MONO model.
    assert {n.model for n in client.added} == {"MONO Basic", "MONO Cloze"}
    assert report.added == 1 and report.skipped == 1
    assert report.apkg_path is None


def test_sync_triggered_only_when_requested(tmp_path):
    jsonl = tmp_path / "s.jsonl"
    _write_facts(jsonl)

    client = FakeClient(available=True)
    import_cards(jsonl, client=client, sync=False)
    assert client.synced is False

    client2 = FakeClient(available=True)
    report = import_cards(jsonl, client=client2, sync=True)
    assert client2.synced is True
    assert report.synced is True


def test_falls_back_to_apkg_when_anki_unavailable(tmp_path):
    jsonl = tmp_path / "session.jsonl"
    _write_facts(jsonl)
    client = FakeClient(available=False)

    report = import_cards(jsonl, client=client)

    assert report.backend == "apkg"
    assert client.added == []          # never tried to add over HTTP
    assert report.apkg_path is not None
    assert report.apkg_path.exists()
    # Default fallback path sits next to the JSONL, same stem.
    assert report.apkg_path == jsonl.with_suffix(".apkg")
    with zipfile.ZipFile(report.apkg_path) as zf:
        assert any(n.startswith("collection.anki2") for n in zf.namelist())


_REPO_ROOT = Path(__file__).resolve().parent.parent


def test_cli_runs_as_documented_script(tmp_path):
    """SKILL.md runs `python scripts/import_cards.py ...` directly; that form
    must work (repo root resolvable) without Anki running -> .apkg fallback."""
    jsonl = tmp_path / "session.jsonl"
    _write_facts(jsonl)
    out = tmp_path / "session.apkg"

    proc = subprocess.run(
        [sys.executable, "scripts/import_cards.py", str(jsonl),
         "--apkg-out", str(out)],
        cwd=_REPO_ROOT, capture_output=True, text=True,
    )

    assert proc.returncode == 0, proc.stderr
    assert out.exists()


def test_explicit_apkg_out_path_is_honored(tmp_path):
    jsonl = tmp_path / "session.jsonl"
    _write_facts(jsonl)
    out = tmp_path / "deck-export.apkg"

    report = import_cards(jsonl, client=FakeClient(available=False), apkg_out=out)

    assert report.apkg_path == out
    assert out.exists()


def test_format_summary_ankiconnect_mentions_counts_and_sync():
    report = ImportReport(backend="ankiconnect", added=5, skipped=2, synced=True)
    summary = _format_summary(report)
    assert "5 added" in summary and "2 skipped" in summary
    assert "sync" in summary.lower()


def test_format_summary_ankiconnect_omits_sync_when_not_synced():
    summary = _format_summary(ImportReport(backend="ankiconnect", added=1, synced=False))
    assert "sync" not in summary.lower()


def test_mappings_applied_on_live_ankiconnect_path(tmp_path):
    jsonl = tmp_path / "s.jsonl"
    _write_facts(jsonl)  # one qa + one cloze
    client = FakeClient(available=True)
    mappings = {"qa": {"Basic": {"Front": "{front}", "Back": "{back}"}}}

    import_cards(jsonl, client=client, mappings=mappings)

    models = {n.model for n in client.added}
    assert "Basic" in models        # qa was redirected to the stock type
    assert "MONO Cloze" in models   # cloze had no override -> stays MONO


def test_apkg_fallback_ignores_mappings_and_uses_mono(tmp_path):
    # genanki can only build note types we define (MONO), so the offline
    # package must ignore external mappings rather than crash.
    jsonl = tmp_path / "s.jsonl"
    _write_facts(jsonl)
    mappings = {"qa": {"Basic": {"Front": "{front}", "Back": "{back}"}}}
    out = tmp_path / "s.apkg"

    report = import_cards(jsonl, client=FakeClient(available=False),
                          mappings=mappings, apkg_out=out)

    assert report.backend == "apkg"
    assert out.exists()


def test_main_reads_config_and_mappings_files(tmp_path):
    jsonl = tmp_path / "s.jsonl"
    _write_facts(jsonl)
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[anki]\nankiconnect_url = "http://localhost:18765"\n'
        '[target_note_types]\nqa = "Basic"\n'
    )
    maps = tmp_path / "mappings.toml"
    maps.write_text('[qa."Basic"]\nFront = "{front}"\nBack = "{back}"\n')
    out = tmp_path / "s.apkg"

    # Custom URL has no Anki listening -> deterministic .apkg fallback.
    code = main([str(jsonl), "--config", str(cfg), "--mappings", str(maps),
                 "--apkg-out", str(out)])

    assert code == 0
    assert out.exists()


def test_import_applies_default_deck_auto_tag_and_target_model(tmp_path):
    jsonl = tmp_path / "s.jsonl"
    jsonl.write_text(
        '{"type":"qa","content":{"front":"Q","back":"A"},"tags":[]}\n'
    )
    client = FakeClient(available=True)
    mappings = {"qa": {"Basic": {"Front": "{front}", "Back": "{back}"}}}

    import_cards(
        jsonl,
        client=client,
        mappings=mappings,
        target_models={"qa": "Basic"},
        default_deck="Inbox",
        auto_tag="mnemo",
    )

    note = client.added[0]
    assert note.model == "Basic"
    assert note.deck == "Inbox"
    assert note.tags == ["mnemo"]
    assert client.ensured_models == ["Basic"]


def test_live_image_occlusion_uploads_image(tmp_path):
    image = tmp_path / "diagram.png"
    image.write_bytes(b"image")
    jsonl = tmp_path / "io.jsonl"
    jsonl.write_text(
        '{"type":"image_occlusion","content":{"image":"diagram.png",'
        '"masks":[{"shape":"rect","left":0.1,"top":0.2,'
        '"width":0.3,"height":0.2}]},"deck":"Anatomy","tags":[]}\n'
    )
    client = FakeClient(available=True)

    import_cards(jsonl, client=client)

    assert client.added[0].model == "Image Occlusion"
    assert client.ensured_models == ["Image Occlusion"]
    assert image in client.stored_media


def test_offline_image_occlusion_requires_live_anki(tmp_path):
    image = tmp_path / "diagram.png"
    image.write_bytes(b"image")
    jsonl = tmp_path / "io.jsonl"
    jsonl.write_text(
        '{"type":"image_occlusion","content":{"image":"diagram.png",'
        '"masks":[{"shape":"rect","left":0.1,"top":0.2,'
        '"width":0.3,"height":0.2}]},"deck":"Anatomy","tags":[]}\n'
    )
    with pytest.raises(RuntimeError, match="live AnkiConnect"):
        import_cards(jsonl, client=FakeClient(available=False))


def test_main_reports_live_only_image_occlusion_without_traceback(tmp_path, capsys):
    image = tmp_path / "diagram.png"
    image.write_bytes(b"image")
    jsonl = tmp_path / "io.jsonl"
    jsonl.write_text(
        '{"type":"image_occlusion","content":{"image":"diagram.png",'
        '"masks":[{"shape":"rect","left":0.1,"top":0.2,'
        '"width":0.3,"height":0.2}]},"deck":"Anatomy","tags":[]}\n'
    )

    code = main([
        str(jsonl),
        "--url", "http://localhost:18765",
        "--config", str(tmp_path / "absent.toml"),
        "--mappings", str(tmp_path / "absent-mappings.toml"),
    ])

    assert code == 1
    captured = capsys.readouterr()
    assert "live AnkiConnect" in captured.err
    assert "Traceback" not in captured.err


def test_main_returns_zero_and_prints_fallback_summary(tmp_path, capsys):
    # No Anki running here, so main() (real AnkiConnect, unreachable) falls back.
    jsonl = tmp_path / "session.jsonl"
    _write_facts(jsonl)
    out = tmp_path / "session.apkg"

    code = main([str(jsonl), "--apkg-out", str(out)])

    assert code == 0
    assert out.exists()
    assert "import" in capsys.readouterr().out.lower()
