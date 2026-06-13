"""Live import backend: a thin wrapper over the AnkiConnect HTTP API.

AnkiConnect (add-on code 2055492159) exposes a single JSON-RPC-ish endpoint on
http://localhost:8765 while Anki desktop is running. Every action is a POST of
``{"action", "version", "params"}`` returning ``{"result", "error"}``.

This wrapper deliberately stays thin: it ensures decks/models exist, adds notes
(letting AnkiConnect reject duplicates), and can trigger an AnkiWeb sync. If the
endpoint is unreachable, callers fall back to the .apkg exporter.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import requests

from scripts.adapter import AnkiNote
from scripts.note_types import NoteType

DEFAULT_URL = "http://localhost:8765"
API_VERSION = 6
_TIMEOUT_S = 10


class AnkiConnectError(RuntimeError):
    """Raised when AnkiConnect returns an error or an unexpected response."""


@dataclass
class AddResult:
    """Outcome of an add_notes call."""

    added: list[int]
    skipped: int  # notes AnkiConnect refused (duplicates / failures)


class AnkiConnect:
    def __init__(self, url: str = DEFAULT_URL, timeout: float = _TIMEOUT_S):
        self.url = url
        self.timeout = timeout

    # --- core transport -----------------------------------------------------

    def _invoke(self, action: str, **params: Any) -> Any:
        payload = {"action": action, "version": API_VERSION, "params": params}
        response = requests.post(self.url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or "error" not in data or "result" not in data:
            raise AnkiConnectError(f"malformed AnkiConnect response: {data!r}")
        if data["error"] is not None:
            raise AnkiConnectError(str(data["error"]))
        return data["result"]

    def is_available(self) -> bool:
        """True if AnkiConnect answers (Anki desktop open with the add-on)."""
        try:
            self._invoke("version")
            return True
        except (requests.RequestException, AnkiConnectError):
            return False

    # --- decks --------------------------------------------------------------

    def deck_names(self) -> list[str]:
        return list(self._invoke("deckNames"))

    def create_deck(self, name: str) -> int:
        return self._invoke("createDeck", deck=name)

    def ensure_deck(self, name: str) -> None:
        if name not in self.deck_names():
            self.create_deck(name)

    # --- models -------------------------------------------------------------

    def model_names(self) -> list[str]:
        return list(self._invoke("modelNames"))

    def ensure_note_types(self, note_types: Iterable[NoteType]) -> list[str]:
        """Create missing MONO models and refresh existing templates/styling."""
        existing = set(self.model_names())
        created: list[str] = []
        for nt in note_types:
            if nt.name in existing:
                self._invoke(
                    "updateModelTemplates",
                    model={
                        "name": nt.name,
                        "templates": {
                            template.name: {
                                "Front": template.qfmt,
                                "Back": template.afmt,
                            }
                            for template in nt.templates
                        },
                    },
                )
                self._invoke(
                    "updateModelStyling",
                    model={"name": nt.name, "css": nt.css},
                )
                continue
            self._invoke(
                "createModel",
                modelName=nt.name,
                inOrderFields=list(nt.fields),
                css=nt.css,
                isCloze=nt.is_cloze,
                cardTemplates=[
                    {"Name": t.name, "Front": t.qfmt, "Back": t.afmt}
                    for t in nt.templates
                ],
            )
            created.append(nt.name)
        return created

    def ensure_models_exist(self, names: Iterable[str]) -> None:
        """Fail clearly when a configured stock/community model is absent."""
        required = set(names)
        if not required:
            return
        missing = required - set(self.model_names())
        if missing:
            joined = ", ".join(sorted(missing))
            raise AnkiConnectError(
                f"required Anki note type(s) not installed: {joined}"
            )

    # --- media --------------------------------------------------------------

    def store_media_file(self, path: str | Path) -> str:
        """Copy one local file into Anki's collection media directory."""
        path = Path(path)
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return str(self._invoke("storeMediaFile", filename=path.name, data=data))

    def store_media_files(self, paths: Iterable[Path]) -> list[str]:
        return [self.store_media_file(path) for path in paths]

    # --- notes --------------------------------------------------------------

    def find_notes(self, query: str) -> list[int]:
        return list(self._invoke("findNotes", query=query))

    def add_notes(self, notes: list[AnkiNote]) -> AddResult:
        """Add notes; AnkiConnect returns a note id per note, or null if refused."""
        payload = [
            {
                "deckName": n.deck,
                "modelName": n.model,
                "fields": n.fields,
                "tags": n.tags,
                "options": {"allowDuplicate": False},
            }
            for n in notes
        ]
        result = self._invoke("addNotes", notes=payload)
        added = [nid for nid in result if nid is not None]
        skipped = sum(1 for nid in result if nid is None)
        return AddResult(added=added, skipped=skipped)

    # --- sync ---------------------------------------------------------------

    def sync(self) -> None:
        """Trigger an AnkiWeb sync (pushes new cards toward the phone apps)."""
        self._invoke("sync")
