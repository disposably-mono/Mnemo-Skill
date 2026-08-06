"""Command-line entrypoint for MONO note-type export."""

from mnemo.pipeline.export_note_types import export_note_types, main

__all__ = ["export_note_types", "main"]
