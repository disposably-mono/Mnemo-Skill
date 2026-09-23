"""Live import backend: a thin wrapper over the AnkiConnect HTTP API.

AnkiConnect exposes a JSON-RPC-ish endpoint on http://localhost:8765 while
Anki desktop is running. Every action is a POST of
``{"action", "version", "params"}`` returning ``{"result", "error"}``.

Ported and trimmed from the pre-rewrite pipeline's proven design: it ensures
decks/models exist, adds notes, and can trigger an AnkiWeb sync. If the
endpoint is unreachable, callers fall back to the .apkg exporter (export.py).
The old AnkiNote/adapter concept is replaced by note_types.render_fields --
callers pass plain field dicts directly.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from mnemo.anki.note_types import NoteType
from mnemo.config import DEFAULT_URL

API_VERSION = 6
_TIMEOUT_S = 10


class AnkiConnectError(RuntimeError):
    """Raised when AnkiConnect returns an error or an unexpected response."""


def _requests():
    """Import requests only when a live AnkiConnect call is made."""
    import requests

    return requests


@dataclass
class AddResult:
    """Outcome of an add_notes call.

    ``results`` keeps AnkiConnect's per-note-id response in submission
    order (None where a note was skipped/refused), so a caller can identify
    *which* submitted note was skipped -- reporting only an aggregate count
    would make skipped cards unauditable.
    """

    added: list[int]
    skipped: int
    results: list[int | None]


class AnkiConnect:
    def __init__(self, url: str = DEFAULT_URL, timeout: float = _TIMEOUT_S):
        _validate_url(url)
        self.url = url
        self.timeout = timeout

    def _invoke(self, action: str, **params: Any) -> Any:
        requests = _requests()
        payload = {"action": action, "version": API_VERSION, "params": params}
        try:
            response = requests.post(self.url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise AnkiConnectError(f"AnkiConnect {action} request failed: {exc}") from exc
        except ValueError as exc:
            raise AnkiConnectError(f"AnkiConnect {action} returned invalid JSON") from exc
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
        except (ModuleNotFoundError, AnkiConnectError):
            return False
        except _requests().RequestException:
            return False

    # --- decks ---------------------------------------------------------

    def deck_names(self) -> list[str]:
        return list(self._invoke("deckNames"))

    def create_deck(self, name: str) -> int:
        return self._invoke("createDeck", deck=name)

    def ensure_deck(self, name: str) -> None:
        if name not in self.deck_names():
            self.create_deck(name)

    # --- models ----------------------------------------------------------

    def model_names(self) -> list[str]:
        return list(self._invoke("modelNames"))

    def ensure_note_types(self, note_types: Iterable[NoteType]) -> list[str]:
        """Create missing models, or safely add missing fields to existing ones.

        Anki appends fields through ``modelFieldAdd``: existing fields must
        stay in the same order, so a reordered/incompatible schema is
        rejected instead of silently changing notes. This is where the
        RevisionHash field gets added on a pre-rewrite Anki profile whose
        model predates it.
        """
        existing = set(self.model_names())
        created: list[str] = []
        for note_type in note_types:
            if note_type.name in existing:
                self._ensure_model_fields(note_type)
                self._update_model_templates(note_type)
                continue
            self._create_model(note_type)
            created.append(note_type.name)
        return created

    def _create_model(self, note_type: NoteType) -> None:
        self._invoke(
            "createModel",
            modelName=note_type.name,
            inOrderFields=list(note_type.fields),
            css=note_type.css,
            isCloze=note_type.is_cloze,
            cardTemplates=[
                {"Name": t.name, "Front": t.qfmt, "Back": t.afmt} for t in note_type.templates
            ],
        )

    def _ensure_model_fields(self, note_type: NoteType) -> None:
        actual = self._invoke("modelFieldNames", modelName=note_type.name)
        if not isinstance(actual, list) or any(not isinstance(f, str) for f in actual):
            raise AnkiConnectError(f"{note_type.name} returned an invalid field schema")
        expected = list(note_type.fields)
        if actual != expected[: len(actual)]:
            raise AnkiConnectError(
                f"{note_type.name} fields are incompatible with the expected schema; "
                f"got {actual!r}"
            )
        for field_name in expected[len(actual):]:
            self._invoke("modelFieldAdd", modelName=note_type.name, fieldName=field_name)

    def _update_model_templates(self, note_type: NoteType) -> None:
        self._invoke(
            "updateModelTemplates",
            model={
                "name": note_type.name,
                "templates": {
                    t.name: {"Front": t.qfmt, "Back": t.afmt} for t in note_type.templates
                },
            },
        )
        self._invoke("updateModelStyling", model={"name": note_type.name, "css": note_type.css})

    # --- media -----------------------------------------------------------

    def store_media_file(self, path: str | Path) -> str:
        """Copy one local file into Anki's collection media directory.

        Refuses to overwrite an existing file of the same name with
        different content; silently no-ops if the content is identical.
        """
        path = Path(path)
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        existing = self._invoke("retrieveMediaFile", filename=path.name)
        if existing == data:
            return path.name
        if existing and existing != data:
            raise AnkiConnectError(
                f"collection already contains a different file named {path.name!r}; "
                "storing would overwrite it."
            )
        return str(self._invoke("storeMediaFile", filename=path.name, data=data))

    # --- notes -------------------------------------------------------------

    def add_notes(
        self,
        *,
        deck: str,
        model: str,
        fields_list: list[dict[str, str]],
        tags_list: list[list[str]],
    ) -> AddResult:
        """Add notes; AnkiConnect returns a note id per note, or null if refused.

        Re-homes each added note's cards to ``deck`` with ``changeDeck``
        afterward: some Anki/AnkiConnect builds ignore the per-note
        ``deckName`` and route new cards to Default, so pinning makes
        placement deterministic (a harmless no-op otherwise).
        """
        if len(fields_list) != len(tags_list):
            raise AnkiConnectError(
                f"fields_list has {len(fields_list)} entries but tags_list has "
                f"{len(tags_list)}; zip() would silently drop notes"
            )
        payload = [
            {
                "deckName": deck, "modelName": model, "fields": fields, "tags": tags,
                "options": {"allowDuplicate": False},
            }
            for fields, tags in zip(fields_list, tags_list)
        ]
        result = self._invoke("addNotes", notes=payload)
        if not isinstance(result, list) or len(result) != len(payload):
            actual = len(result) if isinstance(result, list) else type(result).__name__
            raise AnkiConnectError(
                f"addNotes returned {actual} result(s) for {len(payload)} submitted note(s)"
            )
        note_ids = [nid for nid in result if nid is not None]
        skipped = len(result) - len(note_ids)
        self._pin_deck(note_ids, deck)
        return AddResult(added=note_ids, skipped=skipped, results=list(result))

    def _pin_deck(self, note_ids: list[int], deck: str) -> None:
        """Force freshly-added notes' cards into ``deck``, verifying order defensively."""
        if not note_ids:
            return
        infos = self._invoke("notesInfo", notes=note_ids)
        if not isinstance(infos, list) or len(infos) != len(note_ids):
            raise AnkiConnectError("notesInfo returned an unexpected result; cannot pin decks")
        card_ids: list[int] = []
        for expected_id, info in zip(note_ids, infos):
            if not isinstance(info, dict) or info.get("noteId") != expected_id:
                raise AnkiConnectError(
                    f"notesInfo order mismatch for note {expected_id}; cannot pin decks"
                )
            card_ids.extend(info.get("cards", []))
        if card_ids:
            self._invoke("changeDeck", cards=card_ids, deck=deck)

    def update_note_by_card_id(
        self, card_id: str, model: str, fields: dict[str, str]
    ) -> bool:
        """Update one matching note in place; return False when it is absent."""
        note_ids = self._invoke("findNotes", query=f'CardID:"{card_id}"')
        if not isinstance(note_ids, list) or any(type(note_id) is not int for note_id in note_ids):
            raise AnkiConnectError("findNotes returned an invalid CardID match result")
        if not note_ids:
            return False
        if len(note_ids) != 1:
            raise AnkiConnectError(f"CardID {card_id!r} matched multiple notes")

        note_id = note_ids[0]
        info = self._note_info(note_id)
        if info["modelName"] != model:
            raise AnkiConnectError(
                f"CardID {card_id!r} belongs to {info['modelName']!r}, expected {model!r}"
            )
        actual_card_id = info["fields"]["CardID"]["value"]
        if actual_card_id != card_id:
            raise AnkiConnectError(
                f"CardID {card_id!r} lookup returned note {note_id} "
                f"with CardID {actual_card_id!r}; refusing to update"
            )
        self._invoke("updateNoteFields", note={"id": note_id, "fields": fields})
        return True

    def _note_info(self, note_id: int) -> dict[str, Any]:
        infos = self._invoke("notesInfo", notes=[note_id])
        if not isinstance(infos, list) or len(infos) != 1:
            raise AnkiConnectError(f"notesInfo returned an invalid result for note {note_id}")
        info = infos[0]
        if (
            not isinstance(info, dict)
            or type(info.get("noteId")) is not int
            or info["noteId"] != note_id
            or not isinstance(info.get("modelName"), str)
            or not info["modelName"]
        ):
            raise AnkiConnectError(f"notesInfo returned invalid note or model data for note {note_id}")
        fields = info.get("fields")
        card_id_field = fields.get("CardID") if isinstance(fields, dict) else None
        if not isinstance(card_id_field, dict) or not isinstance(card_id_field.get("value"), str):
            raise AnkiConnectError(f"notesInfo returned invalid CardID field for note {note_id}")
        return info

    # --- sync --------------------------------------------------------------

    def sync(self) -> None:
        self._invoke("sync")


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "http" or parsed.hostname not in local_hosts:
        raise AnkiConnectError(
            "AnkiConnect URL must be an http URL on localhost, 127.0.0.1, or ::1"
        )
