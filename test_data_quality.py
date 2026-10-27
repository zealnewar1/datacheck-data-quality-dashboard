import pandas as pd
from data_quality import missing_summary, rows_with_missing


def make_df():
    return pd.DataFrame({
        "name": ["Ann", None, "Cara", "   "],
        "age": [30, 25, None, 40],
    })


def test_missing_summary_counts_nan_and_blank_text():
    summary = missing_summary(make_df()).set_index("Column")
    assert summary.loc["name", "Missing Count"] == 2   # None + "   "
    assert summary.loc["age", "Missing Count"] == 1


def test_rows_with_missing_reports_file_rows_and_columns():
    result = rows_with_missing(make_df())
    assert result["File Row"].tolist() == [3, 4, 5]
    assert result.loc[result["File Row"] == 4, "Missing In"].iloc[0] == "age"


def test_no_missing_and_empty_input():
    clean = pd.DataFrame({"a": [1, 2]})
    assert rows_with_missing(clean).empty
    assert missing_summary(pd.DataFrame({"a": []}))["Missing Count"].tolist() == [0]


# ---------- Day 5 tests ----------
from data_quality import exact_duplicates, duplicate_ids, guess_id_column


def dup_df():
    return pd.DataFrame({
        "customer_id": ["A", "A", "B", "B", None, None],
        "name": ["Ann", "Ann", "Bob", "Bobby", "X", "Y"],
    })


def test_exact_duplicates_marks_first_and_extra_copy():
    result = exact_duplicates(dup_df())
    assert result["File Row"].tolist() == [2, 3]
    assert result["Status"].tolist() == ["First copy", "Extra copy"]
    assert result["Duplicate Group"].nunique() == 1


def test_duplicate_ids_separates_identical_from_different_and_skips_blanks():
    result = duplicate_ids(dup_df(), "customer_id")
    assert result["File Row"].tolist() == [2, 3, 4, 5]          # blank IDs excluded
    assert result["Issue"].tolist() == [
        "Same ID, identical row", "Same ID, identical row",
        "Same ID, different details", "Same ID, different details",
    ]


def test_no_duplicates_returns_empty():
    clean = pd.DataFrame({"id": [1, 2], "v": ["a", "b"]})
    assert exact_duplicates(clean).empty
    assert duplicate_ids(clean, "id").empty


def test_guess_id_column():
    assert guess_id_column(pd.DataFrame({"name": [1], "customer_id": [2]})) == "customer_id"
    assert guess_id_column(pd.DataFrame({"name": [1]})) is None


# ---------- Day 6 tests ----------
from data_quality import (
    check_email, check_range, check_required, default_rules, run_checks,
)


def people():
    return pd.DataFrame({
        "customer_id": ["C1", "", "C3", "C4"],
        "email": ["a@example.com", "bad.example.com", None, "x@@example.com"],
        "age": [30, -5, "abc", 150],
    })


def test_required_flags_blank_and_whitespace_ids():
    result = check_required(people(), ["customer_id"])
    assert result["File Row"].tolist() == [3]
    assert result["Value"].tolist() == ["(blank)"]


def test_email_flags_invalid_but_skips_blank():
    result = check_email(people(), "email")
    assert result["File Row"].tolist() == [3, 5]     # blank email on row 4 is skipped
    assert check_email(pd.DataFrame({"e": ["a@b.com", "first.last@mail.co.in"]}), "e").empty


def test_email_rejects_common_mistakes():
    bad = ["no-at.com", "a@b", "a@@b.com", "@b.com", "a b@c.com", "a@b..com", "a@b.com "]
    df = pd.DataFrame({"e": bad})
    assert len(check_email(df, "e")) == len(bad)


def test_range_flags_out_of_range_and_non_numbers():
    result = check_range(people(), "age", 0, 120)
    assert result["File Row"].tolist() == [3, 4, 5]
    assert result["Problem"].tolist()[1] == "Not a number"


def test_run_checks_ignores_missing_columns_and_handles_empty_input():
    df = people()
    assert run_checks(df, required=["nope"], email=["nope"], numeric_range=("nope", 0, 1)).empty
    assert run_checks(pd.DataFrame({"a": []}), required=["a"]).empty


def test_default_rules_use_existing_columns_only():
    rules = default_rules(people())
    assert rules["required"] == ["customer_id", "email"]
    assert rules["email"] == ["email"]
    assert rules["range_column"] == "age"
    assert default_rules(pd.DataFrame({"x": [1]}))["range_column"] is None