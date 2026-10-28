"""Day 10: what happens when the data has no rows, one row, or only blanks."""
import pandas as pd

from cleaning import clean_data
from data_quality import (
    default_rules,
    duplicate_ids,
    exact_duplicates,
    guess_id_column,
    missing_mask,
    missing_summary,
    rows_with_missing,
    run_checks,
)
from quality_summary import flagged_records, quality_summary
from reports import build_issue_report


def headers_only():
    """A customer table with the right columns but no rows."""
    return pd.DataFrame({
        "customer_id": pd.Series([], dtype=object),
        "name": pd.Series([], dtype=object),
        "email": pd.Series([], dtype=object),
        "age": pd.Series([], dtype=float),
    })


def one_clean_row():
    return pd.DataFrame({
        "customer_id": ["C001"],
        "name": ["Asha"],
        "email": ["asha@example.com"],
        "age": [30.0],
    })


# ---------- No rows ----------

def test_no_rows_means_no_missing_values():
    assert int(missing_mask(headers_only()).sum().sum()) == 0


def test_missing_summary_handles_no_rows():
    summary = missing_summary(headers_only())
    assert len(summary) == 4  # still one line per column


def test_rows_with_missing_is_empty_for_no_rows():
    assert rows_with_missing(headers_only()).empty


def test_no_rows_means_no_duplicates():
    df = headers_only()
    assert exact_duplicates(df).empty
    assert duplicate_ids(df, "customer_id").empty


def test_validation_finds_nothing_in_no_rows():
    issues = run_checks(
        headers_only(),
        required=["customer_id", "name"],
        email=["email"],
        numeric_range=("age", 0, 120),
    )
    assert issues.empty


def test_default_rules_and_id_guess_work_for_no_rows():
    df = headers_only()
    rules = default_rules(df)
    for key in ("required", "email", "range_column", "range_min", "range_max"):
        assert key in rules
    guess_id_column(df)  # must simply not crash


def test_whole_pipeline_survives_no_rows():
    df = headers_only()
    assert quality_summary(df, "customer_id")["score"] == 100.0
    assert flagged_records(df, "customer_id").empty
    cleaned, stats = clean_data(df, remove_duplicates=True, drop_missing=True)
    assert cleaned.empty and stats["duplicates_removed"] == 0
    assert build_issue_report(df, "customer_id")["Summary"] is not None


# ---------- One row ----------

def test_a_single_clean_row_has_no_issues():
    df = one_clean_row()
    assert rows_with_missing(df).empty
    assert exact_duplicates(df).empty
    assert duplicate_ids(df, "customer_id").empty
    issues = run_checks(
        df,
        required=["customer_id", "name"],
        email=["email"],
        numeric_range=("age", 0, 120),
    )
    assert issues.empty
    assert quality_summary(df, "customer_id", issues)["score"] == 100.0


# ---------- All blanks ----------

def test_a_column_that_is_entirely_blank_counts_every_cell():
    df = pd.DataFrame({"id": [1, 2, 3], "note": [None, "", "  "]})
    assert int(missing_mask(df)["note"].sum()) == 3
    assert rows_with_missing(df).shape[0] == 3


def test_every_row_flagged_gives_a_score_of_zero():
    df = pd.DataFrame({"id": [1, 2], "note": ["", None]})
    assert quality_summary(df)["score"] == 0.0