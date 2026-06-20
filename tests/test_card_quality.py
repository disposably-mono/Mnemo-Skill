import csv

from scripts.audit_cards import build_report, main, print_report


CARD_FIELDS = ("Front", "Back", "Extra", "Mnemonic", "CardType", "Tags")
APPROVAL_FIELDS = ("card_id", "decision", "edited_fields", "reason")


def write_csv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def card_row(back="one"):
    return {
        "Front": "What is alpha?",
        "Back": back,
        "Extra": "Explanation: Alpha is the first item. Context: Test terminology.",
        "Mnemonic": "",
        "CardType": "qa",
        "Tags": "test",
    }


def approval_rows(approved, rejected):
    rows = [
        {"card_id": f"a{index}", "decision": "approved", "edited_fields": "", "reason": ""}
        for index in range(approved)
    ]
    rows.extend(
        {
            "card_id": f"r{index}",
            "decision": "rejected",
            "edited_fields": "",
            "reason": "unsupported claim",
        }
        for index in range(rejected)
    )
    return rows


def test_approval_log_adds_first_pass_calibration_to_audit_report(tmp_path):
    deck = write_csv(tmp_path / "deck.csv", CARD_FIELDS, [card_row()])
    approval_log = write_csv(
        tmp_path / "approvals.csv",
        APPROVAL_FIELDS,
        approval_rows(9, 1),
    )

    report = build_report(deck, approval_log=approval_log)

    assert report["calibration"]["approval"]["first_pass_approval_rate"] == 0.9


def test_missing_approval_log_marks_calibration_approval_not_provided(tmp_path):
    deck = write_csv(tmp_path / "deck.csv", CARD_FIELDS, [card_row()])

    report = build_report(deck)

    assert report["calibration"]["approval"] == {"status": "not-provided"}


def test_nonexistent_approval_log_path_does_not_crash(tmp_path):
    deck = write_csv(tmp_path / "deck.csv", CARD_FIELDS, [card_row()])

    report = build_report(deck, approval_log=tmp_path / "missing.csv")

    assert report["calibration"]["approval"] == {"status": "not-provided"}


def test_cli_nonexistent_approval_log_exits_cleanly(tmp_path):
    deck = write_csv(tmp_path / "deck.csv", CARD_FIELDS, [card_row()])

    assert main([str(deck), "--approval-log", str(tmp_path / "missing.csv")]) == 0


def test_approval_data_does_not_change_passing_or_failing_audit_status(tmp_path):
    passing_deck = write_csv(tmp_path / "passing.csv", CARD_FIELDS, [card_row()])
    failing_deck = write_csv(tmp_path / "failing.csv", CARD_FIELDS, [card_row(back="")])
    approval_log = write_csv(
        tmp_path / "approvals.csv",
        APPROVAL_FIELDS,
        approval_rows(9, 1),
    )

    passing_status = build_report(passing_deck)["status"]
    passing_status_with_approval = build_report(
        passing_deck,
        approval_log=approval_log,
    )["status"]
    failing_status = build_report(failing_deck)["status"]
    failing_status_with_approval = build_report(
        failing_deck,
        approval_log=approval_log,
    )["status"]

    assert passing_status_with_approval == passing_status == "PASS"
    assert failing_status_with_approval == failing_status == "FAIL"


def test_print_report_shows_first_pass_calibration_when_approval_data_exists(
    tmp_path,
    capsys,
):
    deck = write_csv(tmp_path / "deck.csv", CARD_FIELDS, [card_row()])
    approval_log = write_csv(
        tmp_path / "approvals.csv",
        APPROVAL_FIELDS,
        approval_rows(9, 1),
    )
    report = build_report(deck, approval_log=approval_log)

    print_report(report)
    output = capsys.readouterr()

    assert "Calibration: 9/10 first-pass (rate=0.9)" in output.out


def test_approval_log_cli_argument_preserves_passing_exit_code(tmp_path, capsys):
    deck = write_csv(tmp_path / "deck.csv", CARD_FIELDS, [card_row()])
    approval_log = write_csv(
        tmp_path / "approvals.csv",
        APPROVAL_FIELDS,
        approval_rows(9, 1),
    )

    status_without_approval = main([str(deck)])
    capsys.readouterr()
    status_with_approval = main(
        [str(deck), "--approval-log", str(approval_log)]
    )
    capsys.readouterr()

    assert status_with_approval == status_without_approval == 0
