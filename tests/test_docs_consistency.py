from pathlib import Path


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


def test_docs_reference_workspace_and_commands() -> None:
    root = Path(__file__).parents[1]
    documentation = "\n".join(
        (root / path).read_text() if (root / path).is_file() else ""
        for path in DOCUMENTATION_FILES
    )

    missing_references = [
        reference for reference in REQUIRED_REFERENCES if reference not in documentation
    ]

    assert not missing_references, f"Missing documentation references: {missing_references}"
