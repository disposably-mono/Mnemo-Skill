from pathlib import Path

import pytest


DOCUMENTATION_FILES = (
    "README.md",
    "SKILL.md",
    "docs/architecture.md",
    "docs/workflow.md",
    "docs/naming-conventions.md",
)

REQUIRED_REFERENCES = (
    "workspace/courses",
    "mnemo-ingest",
    "mnemo-generate",
    "mnemo-audit",
    "mnemo-import",
    "mnemo-export-note-types",
    "python scripts/ingest.py",
)


def _read_documentation(root: Path) -> str:
    documentation_paths = tuple(root / path for path in DOCUMENTATION_FILES)
    missing_paths = tuple(
        path for path in documentation_paths if not path.is_file()
    )
    assert not missing_paths, f"Missing required documentation files: {missing_paths}"
    return "\n".join(path.read_text() for path in documentation_paths)


def test_documentation_loader_rejects_missing_required_file(tmp_path: Path) -> None:
    for path in DOCUMENTATION_FILES[:-1]:
        documentation_path = tmp_path / path
        documentation_path.parent.mkdir(parents=True, exist_ok=True)
        documentation_path.write_text("placeholder")

    with pytest.raises(AssertionError, match="naming-conventions.md"):
        _read_documentation(tmp_path)


def test_docs_reference_workspace_and_commands() -> None:
    root = Path(__file__).parents[1]
    documentation = _read_documentation(root)

    missing_references = [
        reference for reference in REQUIRED_REFERENCES if reference not in documentation
    ]

    assert not missing_references, f"Missing documentation references: {missing_references}"
