import csv
import json

from scripts.calibrate import build_report, main


APPROVAL_FIELDS = ("card_id", "decision", "edited_fields", "reason")
RETENTION_FIELDS = ("card_id", "interval_days", "predicted_retention", "actual_recalled")


def write_csv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


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


def test_nine_of_ten_approvals_meet_the_first_pass_target(tmp_path):
    log = write_csv(tmp_path / "approvals.csv", APPROVAL_FIELDS, approval_rows(9, 1))

    report = build_report(approval_log=log)

    assert report["approval"]["first_pass_approval_rate"] == 0.9
    assert report["approval"]["meets_90pct_target"] is True


def test_eight_of_ten_approvals_do_not_meet_the_first_pass_target(tmp_path):
    log = write_csv(tmp_path / "approvals.csv", APPROVAL_FIELDS, approval_rows(8, 2))

    report = build_report(approval_log=log)

    assert report["approval"]["first_pass_approval_rate"] == 0.8
    assert report["approval"]["meets_90pct_target"] is False


def test_empty_approval_log_does_not_claim_target_success(tmp_path):
    log = write_csv(tmp_path / "approvals.csv", APPROVAL_FIELDS, [])

    report = build_report(approval_log=log)

    assert report["approval"]["total"] == 0
    assert report["approval"]["first_pass_approval_rate"] is None
    assert report["approval"]["meets_90pct_target"] is None
    assert report["retention"] == {"status": "not-provided"}


def test_missing_approval_argument_is_marked_not_provided(tmp_path):
    rows = [{"card_id": "a1", "interval_days": "5", "predicted_retention": "0.8", "actual_recalled": "1"}]
    retention = write_csv(tmp_path / "retention.csv", RETENTION_FIELDS, rows)

    report = build_report(retention_log=retention)

    assert report["approval"] == {"status": "not-provided"}
    assert report["rejection_reasons"] == {}
    assert report["edit_hotspots"] == {}


def test_rejection_reasons_and_edit_hotspots_are_sorted_by_count(tmp_path):
    rows = [
        {"card_id": "1", "decision": "rejected", "edited_fields": "", "reason": "unsupported"},
        {"card_id": "2", "decision": "rejected", "edited_fields": "", "reason": "ambiguous"},
        {"card_id": "3", "decision": "rejected", "edited_fields": "", "reason": "unsupported"},
        {"card_id": "4", "decision": "edited", "edited_fields": "Front;Back", "reason": "long"},
        {"card_id": "5", "decision": "edited", "edited_fields": "Front", "reason": "long"},
    ]
    log = write_csv(tmp_path / "approvals.csv", APPROVAL_FIELDS, rows)

    report = build_report(approval_log=log)

    assert list(report["rejection_reasons"].items()) == [("unsupported", 2), ("ambiguous", 1)]
    assert list(report["edit_hotspots"].items()) == [("Front", 2), ("Back", 1)]


def test_invalid_decision_is_counted_without_stopping_analysis(tmp_path):
    rows = [
        {"card_id": "1", "decision": "APPROVED", "edited_fields": "", "reason": ""},
        {"card_id": "2", "decision": "deferred", "edited_fields": "", "reason": "later"},
    ]
    log = write_csv(tmp_path / "approvals.csv", APPROVAL_FIELDS, rows)

    report = build_report(approval_log=log)

    assert report["approval"]["total"] == 1
    assert report["approval"]["approved"] == 1
    assert report["approval"]["invalid_rows"] == 1


def test_mature_retention_rows_produce_brier_score_and_buckets(tmp_path):
    rows = [
        {"card_id": "1", "interval_days": "22", "predicted_retention": "0.8", "actual_recalled": "1"},
        {"card_id": "2", "interval_days": "30", "predicted_retention": "0.6", "actual_recalled": "0"},
        {"card_id": "3", "interval_days": "21", "predicted_retention": "0.9", "actual_recalled": "1"},
    ]
    log = write_csv(tmp_path / "retention.csv", RETENTION_FIELDS, rows)

    report = build_report(retention_log=log)

    assert report["retention"]["mature_reviews"] == 2
    assert report["retention"]["brier_score"] == 0.2
    assert report["retention"]["buckets"] == [
        {"predicted_range": "0.6-0.7", "mean_predicted": 0.6, "mean_actual": 0.0, "n": 1},
        {"predicted_range": "0.8-0.9", "mean_predicted": 0.8, "mean_actual": 1.0, "n": 1},
    ]


def test_only_immature_retention_rows_leave_brier_unasserted(tmp_path):
    rows = [{"card_id": "1", "interval_days": "21", "predicted_retention": "0.8", "actual_recalled": "1"}]
    log = write_csv(tmp_path / "retention.csv", RETENTION_FIELDS, rows)

    report = build_report(retention_log=log)

    assert report["retention"]["brier_score"] is None
    assert report["retention"]["buckets"] == []


def test_cli_requires_a_log_and_writes_parseable_json(tmp_path, capsys):
    missing_status = main([])
    missing_output = capsys.readouterr()
    log = write_csv(tmp_path / "approvals.csv", APPROVAL_FIELDS, approval_rows(1, 0))

    json_status = main(["--approval-log", str(log), "--json"])
    json_output = capsys.readouterr()

    assert missing_status == 2
    assert "required" in missing_output.err
    assert json_status == 0
    assert json.loads(json_output.out)["approval"]["approved"] == 1
