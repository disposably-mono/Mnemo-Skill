"""Compatibility re-export for the moved media helpers."""

from ._compat import ensure_src_on_path

ensure_src_on_path()

from mnemo.anki.media import *  # noqa: F403
