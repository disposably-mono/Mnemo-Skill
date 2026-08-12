from pathlib import Path
import subprocess


WORKSPACE_FILES = (
    "workspace/README.md",
    "workspace/courses/_template/README.md",
    "workspace/courses/_template/course.yaml",
    "workspace/courses/_template/00-module-template/README.md",
    "workspace/courses/_template/00-module-template/module.yaml",
    "workspace/courses/_template/00-module-template/source-materials/.gitkeep",
    "workspace/courses/_template/00-module-template/cornell-notes/cornell-note.template.md",
    "workspace/courses/_template/00-module-template/cards/.gitkeep",
    "workspace/courses/_template/00-module-template/exports/.gitkeep",
)


def run_git_check_ignore(path: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "check-ignore", "--no-index", path],
        check=False,
        capture_output=True,
        text=True,
    )


def test_workspace_template_files_exist() -> None:
    root = Path(__file__).parents[1]

    missing_files = [path for path in WORKSPACE_FILES if not (root / path).is_file()]

    assert not missing_files, f"Missing workspace files: {missing_files}"


def test_workspace_private_outputs_are_ignored() -> None:
    private_files = (
        "workspace/courses/biology/source-materials/lecture.pdf",
        "workspace/courses/biology/cornell-notes/module-01.md",
        "workspace/courses/biology/cards/module-01.md",
        "workspace/courses/biology/exports/module-01.apkg",
    )

    results = [run_git_check_ignore(path) for path in private_files]

    assert all(result.returncode == 0 for result in results)


def test_workspace_private_files_with_template_like_names_are_ignored() -> None:
    private_files = (
        "workspace/courses/biology/source-materials/private.yaml",
        "workspace/courses/biology/cards/README.md",
        "workspace/courses/biology/cornell-notes/private.template.md",
        "workspace/courses/biology/exports/private.gitkeep",
    )

    results = [run_git_check_ignore(path) for path in private_files]

    assert all(result.returncode == 0 for result in results)


def test_workspace_templates_are_not_ignored() -> None:
    tracked_files = (
        "workspace/README.md",
        "workspace/courses/_template/README.md",
        "workspace/courses/_template/course.yaml",
        "workspace/courses/_template/00-module-template/README.md",
        "workspace/courses/_template/00-module-template/module.yaml",
        "workspace/courses/_template/00-module-template/cornell-notes/cornell-note.template.md",
        "workspace/courses/_template/00-module-template/source-materials/.gitkeep",
        "workspace/courses/_template/00-module-template/cards/.gitkeep",
        "workspace/courses/_template/00-module-template/exports/.gitkeep",
    )

    results = [run_git_check_ignore(path) for path in tracked_files]

    assert all(result.returncode == 1 and result.stdout == "" for result in results)


def test_workspace_create_builds_course_module_folders_and_metadata(tmp_path) -> None:
    from mnemo.pipeline.workspace import main as workspace_main

    root = tmp_path / "workspace" / "courses"

    assert workspace_main(
        [
            "create",
            "Science 11",
            "1",
            "--title",
            "Perspective on Living Systems",
            "--root",
            str(root),
        ]
    ) == 0

    module = root / "science-11" / "01-perspective-on-living-systems"
    assert (root / "science-11" / "course.yaml").read_text(encoding="utf-8") == (
        "courseSlug: science-11\n"
        "courseTitle: Science 11\n"
        "term: local\n"
        'defaultDeck: "Mnemo::Science 11"\n'
        "tags:\n"
        "  - science-11\n"
    )
    assert (module / "module.yaml").read_text(encoding="utf-8") == (
        "moduleSlug: 01-perspective-on-living-systems\n"
        "moduleTitle: Perspective on Living Systems\n"
        "courseSlug: science-11\n"
        'deck: "Mnemo::Science 11::Perspective on Living Systems"\n'
        "sourceStatus: pending\n"
        "noteStatus: pending\n"
        "cardStatus: pending\n"
        "tags:\n"
        "  - science-11\n"
    )
    assert (module / "source-materials").is_dir()
    assert (module / "cornell-notes").is_dir()
    assert (module / "cards").is_dir()
    assert (module / "exports").is_dir()


def test_workspace_create_rejects_yaml_control_characters(tmp_path) -> None:
    from mnemo.pipeline.workspace import main as workspace_main

    assert workspace_main(
        [
            "create",
            "Science 11\nterm: hacked",
            "1",
            "--title",
            "Perspective on Living Systems",
            "--root",
            str(tmp_path / "workspace" / "courses"),
        ]
    ) == 2


def test_workspace_create_quotes_yaml_significant_scalars(tmp_path) -> None:
    from mnemo.pipeline.workspace import main as workspace_main

    root = tmp_path / "workspace" / "courses"

    assert workspace_main(
        [
            "create",
            "Science: 11",
            "1",
            "--title",
            "Perspective: Living Systems",
            "--root",
            str(root),
            "--term",
            "term: local",
        ]
    ) == 0

    module = root / "science-11" / "01-perspective-living-systems"
    course_yaml = (root / "science-11" / "course.yaml").read_text(encoding="utf-8")
    module_yaml = (module / "module.yaml").read_text(encoding="utf-8")
    assert 'courseTitle: "Science: 11"' in course_yaml
    assert 'term: "term: local"' in course_yaml
    assert 'moduleTitle: "Perspective: Living Systems"' in module_yaml
