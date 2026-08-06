"""Compatibility re-export for the moved AnkiConnect client."""

from ._compat import ensure_src_on_path

ensure_src_on_path()

from mnemo.anki.anki_connect import *  # noqa: F403
