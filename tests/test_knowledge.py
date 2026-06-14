import pytest

from scripts.knowledge import (
    KnowledgeUnit,
    KnowledgeValidationError,
    LearningObjective,
    build_coverage_report,
    classify_knowledge,
)


@pytest.mark.parametrize(
    ("text", "kind", "purpose"),
    [
        ("A differs from B because its scope is narrower.", "comparison", "discriminate"),
        ("First collect data, then clean it.", "ordered-process", "sequence"),
        ("The evidence supports the claim; therefore the policy should change.", "argument", "interpret"),
        ("After the treaty, the alliance collapsed.", "narrative", "sequence"),
        ("Expected value = probability * payoff", "formula", "apply"),
        ("This applies except when demand is perfectly inelastic.", "exception", "discriminate"),
    ],
)
def test_domain_neutral_classification(text, kind, purpose):
    assert classify_knowledge(text) == (kind, purpose)


def test_coverage_records_represented_and_deferred_units():
    objective = LearningObjective("o1", "Explain the model", "Model", "notes.md", True)
    units = [
        KnowledgeUnit("u1", "A is B", "definition", "recall", "Model", "notes.md:1", ["o1"]),
        KnowledgeUnit("u2", "Ambiguous fragment", "fact", "recall", "Model", "notes.md:2", ["o1"], status="deferred"),
    ]

    report = build_coverage_report([objective], units)

    assert report["objectives"][0]["status"] == "covered"
    assert report["summary"]["represented"] == 1
    assert report["summary"]["deferred"] == 1


def test_invalid_semantic_confidence_is_rejected():
    with pytest.raises(KnowledgeValidationError, match="confidence"):
        KnowledgeUnit("u", "text", "fact", "recall", "T", "s", confidence=1.2)
