"""Tests for stable source/fact identities and revision propagation."""

from mnemo.anki.adapter import adapt
from mnemo.anki.note_types import (
    MONO_BASIC,
    MONO_CLOZE,
    MONO_CODE,
    MONO_OVERLAPPING,
    MONO_TYPE,
)
from mnemo.core.card_schema import Fact
from mnemo.core.identity import fact_id, revision_hash, segment_id, source_version_id
from mnemo.pipeline.import_refined_csv import (
    REFINED_BASIC,
    REFINED_CLOZE,
    REFINED_MAPPINGS,
    REFINED_TYPED,
)


def _qa_fact(**overrides) -> Fact:
    data = {
        "type": "qa",
        "content": {"front": "What is ATP synthase?", "back": "An enzyme."},
        "deck": "Biology",
        "tags": ["bio"],
        "source": "lecture.pdf p.2",
        "id": "fact-atp",
        "knowledge_unit_id": "unit-atp",
        "revision_hash": "rev-atp-v1",
    }
    data.update(overrides)
    return Fact.from_dict(data)


def test_source_version_id_is_content_addressed():
    logical_source_id = "logical-source-1"

    first = source_version_id(logical_source_id, b"normalized bytes")
    again = source_version_id(logical_source_id, b"normalized bytes")
    changed = source_version_id(logical_source_id, b"changed bytes")

    assert first == again
    assert first != changed


def test_segment_id_normalizes_text_and_location_shape():
    source_version = source_version_id("logical-source-1", b"normalized bytes")

    first = segment_id(
        source_version,
        {"page": 4, "line_start": 10, "line_end": 11},
        " ATP   synthase\nuses  a proton gradient. ",
    )
    again = segment_id(
        source_version,
        {"line_end": 11, "line_start": 10, "page": 4},
        "ATP synthase uses a proton gradient.",
    )
    moved = segment_id(
        source_version,
        {"page": 5, "line_start": 10, "line_end": 11},
        "ATP synthase uses a proton gradient.",
    )

    assert first == again
    assert first != moved


def test_fact_id_is_semantic_while_revision_hash_tracks_editorial_changes():
    semantic_id = fact_id("unit-atp", "recall", "qa")
    revised_semantic_id = fact_id("unit-atp", "recall", "qa")
    different_intent = fact_id("unit-atp", "explain", "qa")

    first_revision = revision_hash(
        {
            "type": "qa",
            "content": {
                "front": "What is ATP synthase?",
                "back": "An enzyme.",
                "extra": "It couples proton flow to ATP production.",
            },
            "tags": ["bio"],
            "source": "lecture.pdf p.2",
        }
    )
    edited_revision = revision_hash(
        {
            "type": "qa",
            "content": {
                "front": "What is ATP synthase?",
                "back": "An ATP-producing enzyme.",
                "extra": "It couples proton flow to ATP production.",
            },
            "tags": ["bio"],
            "source": "lecture.pdf p.2",
        }
    )

    assert semantic_id == revised_semantic_id
    assert semantic_id != different_intent
    assert first_revision != edited_revision


def test_fact_round_trip_preserves_revision_hash():
    fact = _qa_fact()

    assert fact.revision_hash == "rev-atp-v1"
    assert fact.to_dict()["revision_hash"] == "rev-atp-v1"


def test_mnemo_owned_note_types_include_identity_fields():
    for note_type in (
        MONO_BASIC,
        MONO_CLOZE,
        MONO_CODE,
        MONO_OVERLAPPING,
        MONO_TYPE,
        REFINED_BASIC,
        REFINED_CLOZE,
        REFINED_TYPED,
    ):
        assert "CardID" in note_type.fields, note_type.name
        assert "RevisionHash" in note_type.fields, note_type.name


def test_default_adapter_persists_fact_id_and_revision_hash():
    note = adapt(_qa_fact())

    assert note.fields["CardID"] == "fact-atp"
    assert note.fields["RevisionHash"] == "rev-atp-v1"


def test_adapter_recomputes_stale_canonical_revision_hash():
    note = adapt(_qa_fact(revision_hash="0" * 64))

    assert note.fields["RevisionHash"] != "0" * 64


def test_revision_hash_changes_when_visible_distractor_changes():
    first = adapt(_qa_fact(revision_hash=None, distractors=[{"text": "A catalyst", "grade": "near"}]))
    second = adapt(_qa_fact(revision_hash=None, distractors=[{"text": "A molecule", "grade": "near"}]))

    assert first.fields["RevisionHash"] != second.fields["RevisionHash"]
def test_mapping_placeholders_expose_revision_hash_without_requiring_extra_fields():
    fact = _qa_fact()

    external_note = adapt(
        fact,
        mappings={"qa": {"Basic": {"Front": "{front}", "Back": "{back}"}}},
    )
    refined_note = adapt(fact, mappings=REFINED_MAPPINGS)
    metadata_note = adapt(
        fact,
        mappings={"qa": {"Custom": {"Meta": "{fact_id}|{revision_hash}"}}},
    )

    assert external_note.fields == {
        "Front": "What is ATP synthase?",
        "Back": "An enzyme.",
    }
    assert refined_note.fields["CardID"] == "fact-atp"
    assert refined_note.fields["RevisionHash"] == "rev-atp-v1"
    assert metadata_note.fields["Meta"] == "fact-atp|rev-atp-v1"
