"""Compatibility re-export for the moved .apkg exporter."""

from ._compat import ensure_src_on_path

ensure_src_on_path()

from mnemo.anki.genanki_export import *  # noqa: F403
