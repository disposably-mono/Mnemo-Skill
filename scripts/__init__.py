"""Mnemo toolkit: ingest study material and author Anki cards.

Modules:
    card_schema       - the Fact contract + validation (central data model)
    config            - optional config.toml loader (url, sync, decks, tags)
    ingest            - source material (pdf/pptx/md) -> normalized text
    adapter           - Fact -> target note-type fields + mappings.toml interop
    note_types        - MONO reference note types (templates + design-system CSS)
    anki_connect      - live import via the AnkiConnect HTTP API
    genanki_export    - .apkg fallback when Anki desktop is not running
    media             - bundled fonts and note-media collection
    import_cards      - orchestrator + CLI (load -> adapt -> import)
    export_note_types - write the MONO note types as an installable .apkg
"""

__version__ = "0.0.1"
