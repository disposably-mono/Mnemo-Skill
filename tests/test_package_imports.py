import importlib.metadata
import subprocess
import sys
import zipfile
from pathlib import Path

import mnemo
import pytest


_REPO_ROOT = Path(__file__).resolve().parents[1]
_PACKAGE_ROOT = _REPO_ROOT / "src" / "mnemo"


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


@pytest.mark.parametrize(
    "script",
    [
        "scripts/import_cards.py",
        "scripts/export_note_types.py",
        "scripts/import_refined_csv.py",
    ],
)
def test_direct_script_help_works_without_site_packages(script):
    """Direct wrappers must find src/ without pytest's configured pythonpath."""
    result = subprocess.run(
        [sys.executable, "-S", script, "--help"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout


def test_bundled_font_paths_extracts_zip_resources_and_keeps_them_available(tmp_path):
    """Zip-installed resources need real paths until Anki has consumed them."""
    archive = tmp_path / "mnemo.zip"
    members = [
        "__init__.py",
        "anki/__init__.py",
        "anki/media.py",
        "resources/__init__.py",
        "resources/fonts/__init__.py",
        *(f"resources/fonts/{path.name}" for path in (_PACKAGE_ROOT / "resources/fonts").glob("*.ttf")),
    ]
    with zipfile.ZipFile(archive, "w") as bundle:
        for member in members:
            bundle.write(_PACKAGE_ROOT / member, f"mnemo/{member}")

    code = """
import gc
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from mnemo.anki.media import bundled_font_paths

paths = bundled_font_paths()
gc.collect()
assert len(paths) == 4
assert all(isinstance(path, Path) and path.is_file() for path in paths)
assert {path.name for path in paths} == {
    '_dmmono-medium.ttf',
    '_dmmono-regular.ttf',
    '_dmserifdisplay-regular.ttf',
    '_outfit-variable.ttf',
}
"""
    result = subprocess.run(
        [sys.executable, "-S", "-c", code, str(archive)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("legacy_module", "package_module", "export_name"),
    [
        ("adapter", "mnemo.anki.adapter", "AnkiNote"),
        ("anki_connect", "mnemo.anki.anki_connect", "AnkiConnect"),
        ("genanki_export", "mnemo.anki.genanki_export", "export_apkg"),
        ("media", "mnemo.anki.media", "bundled_font_paths"),
        ("note_types", "mnemo.anki.note_types", "MONO_BASIC"),
    ],
)
def test_legacy_anki_script_modules_reexport_package_apis(
    legacy_module, package_module, export_name
):
    legacy = __import__(f"scripts.{legacy_module}", fromlist=[export_name])
    package = __import__(package_module, fromlist=[export_name])

    assert getattr(legacy, export_name) is getattr(package, export_name)
