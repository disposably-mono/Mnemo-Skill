"""Compatibility re-export for the moved Anki note types."""

from ._compat import ensure_src_on_path

ensure_src_on_path()

from mnemo.anki.note_types import *  # noqa: F403
