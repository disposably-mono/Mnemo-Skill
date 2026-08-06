"""Recognition helpers for source spans that prose heuristics must not alter."""

from __future__ import annotations

import re


_FENCE_OPEN = re.compile(r"^\s*(?P<marker>`{3,}|~{3,})(?:\s*(?P<language>[^\s`~]+))?\s*$")
_INLINE_SENTINEL = re.compile(r"\x1eVERBATIM:\d+\x1f")


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


def protect_inline_verbatim(text: str) -> tuple[str, list[str]]:
    """Mask inline code and MathJax spans while retaining restoration data."""
    spans: list[str] = []
    parts: list[str] = []
    cursor = 0
    while cursor < len(text):
        end = _inline_span_end(text, cursor)
        if end is None:
            parts.append(text[cursor])
            cursor += 1
            continue
        spans.append(text[cursor:end])
        parts.append(f"\x1eVERBATIM:{len(spans) - 1}\x1f")
        cursor = end
    return "".join(parts), spans


def restore_inline_verbatim(text: str, spans: list[str]) -> str:
    """Restore spans previously returned by :func:`protect_inline_verbatim`."""
    return _INLINE_SENTINEL.sub(
        lambda match: spans[int(match.group()[10:-1])], text
    )


def without_inline_verbatim(text: str) -> str:
    """Return text with inline code and math removed for prose heuristics."""
    masked, _ = protect_inline_verbatim(text)
    return _INLINE_SENTINEL.sub(" ", masked)


def has_inline_verbatim(text: str) -> bool:
    """Return whether text contains a complete inline code or math span."""
    _, spans = protect_inline_verbatim(text)
    return bool(spans)


def _inline_span_end(text: str, start: int) -> int | None:
    character = text[start]
    if character == "`":
        return _matching_end(text, start, "`", "`")
    if text.startswith(r"\(", start):
        return _matching_end(text, start, r"\(", r"\)")
    if character == "$" and not text.startswith("$$", start) and not _is_escaped(text, start):
        return _matching_end(text, start, "$", "$")
    return None


def _matching_end(text: str, start: int, opening: str, closing: str) -> int | None:
    cursor = start + len(opening)
    while cursor < len(text):
        end = text.find(closing, cursor)
        if end < 0 or "\n" in text[cursor:end]:
            return None
        if closing.startswith("\\") or not _is_escaped(text, end):
            return end + len(closing)
        cursor = end + 1
    return None


def _is_escaped(text: str, index: int) -> bool:
    return index > 0 and text[index - 1] == "\\"
