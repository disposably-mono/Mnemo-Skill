"""Tests for the audit rubric (mnemo/audit.py).

Per SKILL.md: errors block import, warnings require conscious review.
Heuristics flag likely compounds and thin explanations but cannot prove
semantic atomicity -- judge each case.
"""

from mnemo.audit import audit_cards, build_report
from mnemo.card import Card


def make_card(**overrides):
    fields = dict(
        front="What organelle produces most cellular ATP?",
        back="The mitochondrion.",
        extra="Explanation: oxidative phosphorylation occurs there.",
        card_type="qa",
        source="notes.md",
    )
    fields.update(overrides)
    return Card(**fields)


def test_clean_deck_has_no_violations():
    cards = [make_card()]
    assert audit_cards(cards) == []


def test_duplicate_front_back_flags_every_card_in_the_group():
    cards = [
        make_card(card_id="c1"), make_card(card_id="c2"), make_card(card_id="c3"),
    ]
    violations = [v for v in audit_cards(cards) if v.code == "DUPLICATE_CARD"]
    assert len(violations) == 3
    assert {v.card_id for v in violations} == {"c1", "c2", "c3"}
    assert all("3 times" in v.message for v in violations)


def test_duplicate_check_is_case_insensitive():
    cards = [
        make_card(front="What is ATP?", back="Adenosine triphosphate."),
        make_card(front="what is atp?", back="ADENOSINE TRIPHOSPHATE."),
    ]
    violations = audit_cards(cards)
    assert any(v.code == "DUPLICATE_CARD" for v in violations)


def test_valid_cloze_card_has_no_cloze_violation():
    card = make_card(
        front="The {{c1::mitochondrion}} produces most cellular ATP.",
        card_type="cloze",
    )
    violations = audit_cards([card])
    assert not any(v.code == "CLOZE_SYNTAX" for v in violations)


def test_cloze_card_without_deletion_is_an_error():
    card = make_card(front="The mitochondrion produces most cellular ATP.", card_type="cloze")
    violations = audit_cards([card])
    assert any(v.code == "CLOZE_SYNTAX" and v.level == "error" for v in violations)


def test_cloze_card_with_unbalanced_braces_is_an_error():
    card = make_card(front="The {{c1::mitochondrion produces ATP.", card_type="cloze")
    violations = audit_cards([card])
    assert any(v.code == "CLOZE_SYNTAX" and v.level == "error" for v in violations)


def test_cloze_card_with_empty_deletion_is_an_error():
    card = make_card(front="The {{c1::}} produces ATP.", card_type="cloze")
    violations = audit_cards([card])
    assert any(v.code == "CLOZE_SYNTAX" and v.level == "error" for v in violations)


def test_cloze_card_with_valid_and_malformed_pair_is_an_error():
    # Brace-balanced overall, and has one genuinely valid deletion -- but the
    # second pair isn't cloze markup at all, so this must still fail.
    card = make_card(
        front="The {{c1::mitochondrion}} produces {{stray}} ATP.", card_type="cloze",
    )
    violations = audit_cards([card])
    cloze_violations = [v for v in violations if v.code == "CLOZE_SYNTAX"]
    assert len(cloze_violations) == 1
    assert cloze_violations[0].level == "error"
    assert "malformed" in cloze_violations[0].message


def test_thin_explanation_is_flagged():
    card = make_card(extra="")
    violations = audit_cards([card])
    assert any(v.code == "THIN_EXPLANATION" and v.level == "warning" for v in violations)


def test_short_prompt_is_flagged_as_generic():
    card = make_card(front="ATP?")
    violations = audit_cards([card])
    assert any(v.code == "GENERIC_PROMPT" for v in violations)


def test_compound_prompt_is_flagged_for_atomicity_review():
    card = make_card(
        front="What produces ATP and what regulates the cell cycle?",
    )
    violations = audit_cards([card])
    assert any(v.code == "ATOMICITY_REVIEW" for v in violations)


def test_missing_source_is_flagged():
    card = make_card(source=None)
    violations = audit_cards([card])
    assert any(v.code == "MISSING_SOURCE" and v.level == "warning" for v in violations)


def test_violation_carries_card_id_when_present():
    card = make_card(card_id="c-0001", extra="")
    violations = audit_cards([card])
    thin = next(v for v in violations if v.code == "THIN_EXPLANATION")
    assert thin.card_id == "c-0001"


def test_build_report_status_pass_with_only_warnings():
    report = build_report([make_card(extra="")])
    assert report.status == "PASS"
    assert report.errors == 0
    assert report.warnings == 1


def test_build_report_status_fail_with_errors():
    card = make_card(front="No deletion here.", card_type="cloze")
    report = build_report([card])
    assert report.status == "FAIL"
    assert report.errors == 1


def test_build_report_summary_counts_cards_and_types():
    report = build_report([make_card(), make_card(card_type="cloze", front="{{c1::x}} y")])
    assert report.card_count == 2
    assert report.card_types == {"qa": 1, "cloze": 1}


def test_build_report_on_empty_deck():
    report = build_report([])
    assert report.status == "PASS"
    assert report.card_count == 0
    assert report.card_types == {}


def test_card_with_multiple_violations_is_flagged_by_each_check():
    card = make_card(front="ATP?", extra="", source=None)
    codes = {v.code for v in audit_cards([card])}
    assert {"GENERIC_PROMPT", "THIN_EXPLANATION", "MISSING_SOURCE"} <= codes
