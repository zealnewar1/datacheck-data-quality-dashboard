from io import BytesIO

import pandas as pd

from data_quality import run_checks
from reports import build_issue_report, report_to_excel_bytes


def summary_value(sheets, measure):
    table = sheets["Summary"]
    return table.loc[table["Measure"] == measure, "Value"].iloc[0]


def test_clean_data_report_has_the_three_core_sheets():
    df = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})
    sheets = build_issue_report(df, id_col="id")
    assert list(sheets) == ["Summary", "Issues by type", "Flagged records"]
    assert summary_value(sheets, "Quality score (%)") == 100.0
    assert sheets["Flagged records"].empty


def test_summary_matches_the_quality_score():
    df = pd.DataFrame({"id": range(1, 11), "email": ["a@b.com"] * 8 + ["", ""]})
    sheets = build_issue_report(df, id_col="id")
    assert summary_value(sheets, "Total rows") == 10
    assert summary_value(sheets, "Rows with issues") == 2
    assert summary_value(sheets, "Quality score (%)") == 80.0
    assert summary_value(sheets, "Customer ID column") == "id"
    assert summary_value(sheets, "Validation rules") == "None selected"


def test_validation_sheet_appears_only_when_issues_exist():
    df = pd.DataFrame({"id": [1, 2], "email": ["a@b.com", "bad"]})
    issues = run_checks(df, email=["email"])
    sheets = build_issue_report(df, id_col="id", issues=issues)
    assert "Validation issues" in sheets
    assert summary_value(sheets, "Validation rules") == "Applied"

    ok = pd.DataFrame({"id": [1], "email": ["a@b.com"]})
    ok_sheets = build_issue_report(ok, id_col="id", issues=run_checks(ok, email=["email"]))
    assert "Validation issues" not in ok_sheets


def test_flagged_records_sheet_explains_each_row():
    df = pd.DataFrame({"id": [1, 2], "email": ["a@b.com", "bad"]})
    issues = run_checks(df, email=["email"])
    flagged = build_issue_report(df, id_col="id", issues=issues)["Flagged records"]
    assert flagged["File Row"].tolist() == [3]
    assert "Email format" in flagged.loc[0, "Problems"]


def test_report_leaves_the_original_unchanged():
    df = pd.DataFrame({"id": [1, 2], "name": ["a", ""]})
    before = df.copy()
    build_issue_report(df, id_col="id")
    assert df.equals(before)


def test_excel_bytes_round_trip():
    df = pd.DataFrame({"id": [1, 2], "email": ["a@b.com", "bad"]})
    issues = run_checks(df, email=["email"])
    sheets = build_issue_report(df, id_col="id", issues=issues)
    data = report_to_excel_bytes(sheets)
    loaded = pd.read_excel(BytesIO(data), sheet_name=None)
    assert set(loaded) == set(sheets)
    assert len(loaded["Flagged records"]) == 1


def test_excel_export_works_when_nothing_is_flagged():
    df = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})
    data = report_to_excel_bytes(build_issue_report(df, id_col="id"))
    loaded = pd.read_excel(BytesIO(data), sheet_name=None)
    assert loaded["Flagged records"].empty


def test_empty_dataframe_does_not_crash():
    df = pd.DataFrame({"id": []})
    sheets = build_issue_report(df, id_col="id")
    assert summary_value(sheets, "Total rows") == 0
    report_to_excel_bytes(sheets)