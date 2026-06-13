"""Mnemo toolkit: ingest study material and author Anki cards.

Modules:
    card_schema     - the Fact contract + validation (central data model)
    ingest          - source material (pdf/pptx/md) -> normalized text
    adapter         - Fact -> target note-type fields (interop layer)
    note_types      - MONO reference note types (templates + design-system CSS)
    anki_connect    - live import via the AnkiConnect HTTP API
    genanki_export  - .apkg fallback when Anki desktop is not running
"""

__version__ = "0.0.1"
