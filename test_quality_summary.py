import pandas as pd

from data_quality import run_checks
from quality_summary import quality_summary


def count_for(summary, issue_type):
    table = summary["table"]
    return int(table.loc[table["Issue type"] == issue_type, "Issues"].iloc[0])


def test_clean_data_scores_100():
    df = pd.DataFrame({"id": [1, 2, 3], "email": ["a@b.com", "c@d.com", "e@f.com"]})
    result = quality_summary(df, id_col="id")
    assert result["score"] == 100.0
    assert result["rows_with_issues"] == 0
    assert result["total_rows"] == 3 and result["total_columns"] == 2


def test_missing_cell_flags_its_row():
    df = pd.DataFrame({"id": [1, 2, 3], "email": ["a@b.com", "", "c@d.com"]})
    result = quality_summary(df, id_col="id")
    assert result["flagged_rows"] == [3]  # index 1 is file row 3
    assert count_for(result, "Missing data") == 1


def test_row_with_many_issues_counts_once():
    df = pd.DataFrame({"id": [1, None, 3], "email": ["a@b.com", None, "bad"]})
    issues = run_checks(df, required=["id", "email"], email=["email"])
    assert len(issues) == 3  # 2 required + 1 bad email
    result = quality_summary(df, id_col="id", issues=issues)
    assert result["flagged_rows"] == [3, 4]
    assert result["rows_with_issues"] == 2


def test_only_extra_copy_is_flagged_for_exact_duplicates():
    df = pd.DataFrame({"id": [1, 2, 2], "name": ["a", "b", "b"]})
    result = quality_summary(df, id_col=None)
    assert result["flagged_rows"] == [4]
    assert count_for(result, "Exact duplicate rows") == 1


def test_conflicting_ids_flag_both_rows_but_identical_rows_do_not_double_count():
    df = pd.DataFrame({
        "id": [1, 1, 2, 2, 3],
        "name": ["a", "b", "c", "c", "d"],
    })
    result = quality_summary(df, id_col="id")
    # ID 1 conflicts (file rows 2 and 3); ID 2 is an identical copy (extra copy = row 5)
    assert result["flagged_rows"] == [2, 3, 5]
    assert count_for(result, "Duplicate customer IDs (conflicting)") == 2
    assert count_for(result, "Exact duplicate rows") == 1


def test_score_arithmetic():
    df = pd.DataFrame({
        "id": range(1, 11),
        "email": ["a@b.com"] * 8 + ["", ""],
    })
    result = quality_summary(df, id_col="id")
    assert result["rows_with_issues"] == 2
    assert result["clean_rows"] == 8
    assert result["score"] == 80.0


def test_validation_rules_appear_in_the_table():
    df = pd.DataFrame({"email": ["a@b.com", "nope"], "age": [30, 150]})
    issues = run_checks(df, email=["email"], numeric_range=("age", 0, 120))
    result = quality_summary(df, issues=issues)
    types = set(result["table"]["Issue type"])
    assert {"Email format", "Number range"} <= types
    assert result["flagged_rows"] == [3]  # one row has both problems, so it counts once


def test_unknown_id_column_is_ignored():
    df = pd.DataFrame({"name": ["a", "b"]})
    result = quality_summary(df, id_col="customer_id")
    assert result["score"] == 100.0


def test_empty_dataframe_does_not_crash():
    df = pd.DataFrame({"id": []})
    result = quality_summary(df, id_col="id")
    assert result["score"] == 100.0
    assert result["total_rows"] == 0