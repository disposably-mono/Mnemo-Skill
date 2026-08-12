"""Pure helpers for stable source, segment, fact, and revision identities."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def source_version_id(logical_source_id: str, normalized_bytes: bytes) -> str:
    """Return a deterministic id for one observed logical-source version."""
    source_id = _require_non_empty_string(logical_source_id, "logical_source_id")
    if not isinstance(normalized_bytes, (bytes, bytearray, memoryview)):
        raise TypeError("normalized_bytes must be bytes-like")
    return _hash_parts(
        "source-version",
        source_id,
        bytes(normalized_bytes),
    )


def segment_id(source_version: str, location: object, text: str) -> str:
    """Return a deterministic id for a source segment within one version."""
    version_id = _require_non_empty_string(source_version, "source_version_id")
    normalized_text = " ".join(_require_non_empty_string(text, "text").split())
    return _hash_parts(
        "segment",
        version_id,
        _canonical_json_bytes(location),
        normalized_text,
    )


def fact_id(unit_id: str, recall_intent: str, fact_type: str) -> str:
    """Return a deterministic semantic fact id."""
    return _hash_parts(
        "fact",
        _require_non_empty_string(unit_id, "unit_id"),
        _require_non_empty_string(recall_intent, "recall_intent"),
        _require_non_empty_string(fact_type, "fact_type"),
    )


def revision_hash(rendered_fact: object) -> str:
    """Return a deterministic hash for rendered note-relevant content."""
    return _hash_parts("revision", _canonical_json_bytes(rendered_fact))


def _hash_parts(namespace: str, *parts: object) -> str:
    digest = hashlib.sha256()
    digest.update(f"mnemo:{namespace}".encode("utf-8"))
    for part in parts:
        digest.update(b"\0")
        digest.update(_to_bytes(part))
    return digest.hexdigest()


def _to_bytes(value: object) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    return _canonical_json_bytes(value)


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        _canonicalize(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _canonicalize(value: object) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _canonicalize(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    raise TypeError(f"value of type {type(value).__name__} is not JSON-serializable")


def _require_non_empty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()
