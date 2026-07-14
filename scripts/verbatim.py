"""Recognition helpers for source spans that prose heuristics must not alter."""

from __future__ import annotations

import re


_FENCE_OPEN = re.compile(r"^\s*(?P<marker>`{3,}|~{3,})(?:\s*(?P<language>[^\s`~]+))?\s*$")


def fenced_code_opening(line: str) -> tuple[str, str] | None:
    """Return a fence marker and optional language for a fenced-code opener."""
    match = _FENCE_OPEN.match(line)
    if match is None:
        return None
    return match.group("marker"), (match.group("language") or "").strip()


def is_fenced_code_closing(line: str, marker: str) -> bool:
    """Return whether ``line`` closes a fenced block opened with ``marker``."""
    return bool(re.fullmatch(rf"\s*{re.escape(marker[0])}{{{len(marker)},}}\s*", line))


def is_display_math_delimiter(line: str) -> bool:
    """Return whether a line is a standalone display-math delimiter."""
    return line.strip() == "$$"


def is_single_line_display_math(line: str) -> bool:
    """Return whether a line contains a complete ``$$ ... $$`` expression."""
    stripped = line.strip()
    return len(stripped) > 4 and stripped.startswith("$$") and stripped.endswith("$$")
