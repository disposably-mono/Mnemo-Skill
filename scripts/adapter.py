"""Compatibility re-export for the moved Anki adapter."""

from ._compat import ensure_src_on_path

ensure_src_on_path()

from mnemo.anki.adapter import *  # noqa: F403
