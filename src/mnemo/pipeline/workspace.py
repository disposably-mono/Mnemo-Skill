"""Create Mnemo course and module workspace folders."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Sequence


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "untitled"


def module_slug(module_number: str, title: str) -> str:
    try:
        prefix = f"{int(module_number):02d}"
    except ValueError:
        prefix = slugify(module_number)
    return f"{prefix}-{slugify(title)}"


def validate_scalar(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    if any(character in value for character in "\r\n\t"):
        raise ValueError(f"{name} must not contain control characters")


def yaml_scalar(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_. -]+", value):
        return value
    return json.dumps(value)


def build_course_yaml(course_title: str, course_slug: str, term: str) -> str:
    return (
        f"courseSlug: {yaml_scalar(course_slug)}\n"
        f"courseTitle: {yaml_scalar(course_title)}\n"
        f"term: {yaml_scalar(term)}\n"
        f"defaultDeck: {yaml_scalar(f'Mnemo::{course_title}')}\n"
        "tags:\n"
        f"  - {yaml_scalar(course_slug)}\n"
    )


def build_module_yaml(course_slug: str, module_title: str, slug: str) -> str:
    return (
        f"moduleSlug: {yaml_scalar(slug)}\n"
        f"moduleTitle: {yaml_scalar(module_title)}\n"
        f"courseSlug: {yaml_scalar(course_slug)}\n"
        "sourceStatus: pending\n"
        "noteStatus: pending\n"
        "cardStatus: pending\n"
        "tags:\n"
        f"  - {yaml_scalar(course_slug)}\n"
    )


def create_workspace(
    course_title: str,
    module_number: str,
    module_title: str,
    *,
    root: Path,
    term: str,
) -> Path:
    validate_scalar(course_title, "course title")
    validate_scalar(module_number, "module number")
    validate_scalar(module_title, "module title")
    validate_scalar(term, "term")
    course_slug = slugify(course_title)
    slug = module_slug(module_number, module_title)
    course_dir = root / course_slug
    module_dir = course_dir / slug
    for name in ("source-materials", "cornell-notes", "cards", "exports"):
        (module_dir / name).mkdir(parents=True, exist_ok=True)
    course_yaml = course_dir / "course.yaml"
    if not course_yaml.exists():
        course_yaml.write_text(build_course_yaml(course_title, course_slug, term), encoding="utf-8")
    module_yaml = module_dir / "module.yaml"
    if not module_yaml.exists():
        module_yaml.write_text(build_module_yaml(course_slug, module_title, slug), encoding="utf-8")
    return module_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create", help="Create a course/module workspace.")
    create.add_argument("course_title")
    create.add_argument("module_number")
    create.add_argument("--title", required=True, help="Module title.")
    create.add_argument("--root", type=Path, default=Path("workspace/courses"))
    create.add_argument("--term", default="local")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "create":
        try:
            module_dir = create_workspace(
                args.course_title,
                args.module_number,
                args.title,
                root=args.root,
                term=args.term,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(module_dir)
        return 0
    return 2
