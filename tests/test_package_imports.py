import importlib.metadata

import mnemo
import pytest


def test_package_exposes_version():
    assert mnemo.__version__ == "0.0.1"


def test_console_scripts_are_declared():
    scripts = {
        entry_point.name
        for entry_point in importlib.metadata.entry_points(group="console_scripts")
    }
    assert "mnemo-ingest" in scripts
    assert "mnemo-generate" in scripts
    assert "mnemo-audit" in scripts
    assert "mnemo-import" in scripts
    assert "mnemo-export-note-types" in scripts


@pytest.mark.parametrize(
    "main",
    [
        __import__("mnemo.cli.ingest", fromlist=["main"]).main,
        __import__("mnemo.cli.generate", fromlist=["main"]).main,
        __import__("mnemo.cli.audit", fromlist=["main"]).main,
        __import__("mnemo.cli.import_cards", fromlist=["main"]).main,
        __import__("mnemo.cli.export_note_types", fromlist=["main"]).main,
    ],
)
def test_temporary_cli_entrypoints_explain_they_are_not_wired(main):
    with pytest.raises(SystemExit, match="Mnemo CLI entrypoint is not wired yet"):
        main()
