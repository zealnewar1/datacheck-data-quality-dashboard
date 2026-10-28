import pandas as pd

from cleaning import (
    FILL_CUSTOM,
    FILL_MEAN,
    FILL_MEDIAN,
    FILL_MODE,
    clean_data,
    fill_missing,
    remove_exact_duplicates,
    remove_rows_with_missing,
)


# ---------- Removing duplicates ----------

def test_remove_exact_duplicates_keeps_first_copy():
    df = pd.DataFrame({"id": [1, 2, 2, 3], "name": ["a", "b", "b", "c"]})
    out, removed = remove_exact_duplicates(df)
    assert removed == 1
    assert out["id"].tolist() == [1, 2, 3]
    assert len(df) == 4  # original untouched


def test_same_id_with_different_details_is_not_removed():
    df = pd.DataFrame({"id": [1, 1], "name": ["a", "b"]})
    out, removed = remove_exact_duplicates(df)
    assert removed == 0
    assert len(out) == 2


def test_no_duplicates_removes_nothing():
    df = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})
    out, removed = remove_exact_duplicates(df)
    assert removed == 0
    assert out.equals(df)


# ---------- Removing rows with missing values ----------

def test_remove_rows_with_missing_counts_blank_text_too():
    df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "", None]})
    out, removed = remove_rows_with_missing(df)
    assert removed == 2
    assert out["id"].tolist() == [1]


# ---------- Filling missing values ----------

def test_fill_custom_text_value():
    df = pd.DataFrame({"city": ["Paris", "", None]})
    out, filled, skipped = fill_missing(df, {"city": {"method": FILL_CUSTOM, "value": "Unknown"}})
    assert out["city"].tolist() == ["Paris", "Unknown", "Unknown"]
    assert filled == 2
    assert skipped == []


def test_fill_most_common_value():
    df = pd.DataFrame({"city": ["Paris", "Paris", "Rome", None]})
    out, filled, _ = fill_missing(df, {"city": {"method": FILL_MODE}})
    assert out["city"].tolist() == ["Paris", "Paris", "Rome", "Paris"]
    assert filled == 1


def test_fill_median_and_mean():
    df = pd.DataFrame({"age": [10.0, 20.0, None, 40.0], "score": [10.0, 20.0, None, 30.0]})
    out, filled, _ = fill_missing(df, {
        "age": {"method": FILL_MEDIAN},
        "score": {"method": FILL_MEAN},
    })
    assert out["age"].tolist() == [10.0, 20.0, 20.0, 40.0]
    assert out["score"].tolist() == [10.0, 20.0, 20.0, 30.0]
    assert filled == 2


def test_custom_number_is_accepted_for_a_numeric_column():
    df = pd.DataFrame({"age": [10.0, None]})
    out, filled, skipped = fill_missing(df, {"age": {"method": FILL_CUSTOM, "value": "0"}})
    assert out["age"].tolist() == [10.0, 0.0]
    assert filled == 1 and skipped == []


def test_median_on_a_text_column_is_skipped_not_guessed():
    df = pd.DataFrame({"city": ["Paris", None]})
    out, filled, skipped = fill_missing(df, {"city": {"method": FILL_MEDIAN}})
    assert filled == 0
    assert skipped[0][0] == "city"
    assert out["city"].isna().tolist() == [False, True]


def test_custom_text_in_a_numeric_column_is_skipped():
    df = pd.DataFrame({"age": [10.0, None]})
    _, filled, skipped = fill_missing(df, {"age": {"method": FILL_CUSTOM, "value": "abc"}})
    assert filled == 0
    assert skipped[0][0] == "age"


def test_custom_fill_with_no_value_is_skipped():
    df = pd.DataFrame({"city": ["Paris", None]})
    _, filled, skipped = fill_missing(df, {"city": {"method": FILL_CUSTOM, "value": "  "}})
    assert filled == 0
    assert len(skipped) == 1


def test_fill_most_common_when_everything_is_missing_is_skipped():
    df = pd.DataFrame({"city": [None, None]})
    _, filled, skipped = fill_missing(df, {"city": {"method": FILL_MODE}})
    assert filled == 0
    assert len(skipped) == 1


def test_unknown_column_is_skipped():
    df = pd.DataFrame({"city": ["Paris"]})
    _, filled, skipped = fill_missing(df, {"nope": {"method": FILL_MODE}})
    assert filled == 0
    assert skipped == [("nope", "Column not found")]


def test_column_with_nothing_missing_is_left_alone():
    df = pd.DataFrame({"city": ["Paris", "Rome"]})
    out, filled, skipped = fill_missing(df, {"city": {"method": FILL_MODE}})
    assert filled == 0 and skipped == []
    assert out.equals(df)


def test_fill_does_not_change_the_original():
    df = pd.DataFrame({"city": ["Paris", None]})
    fill_missing(df, {"city": {"method": FILL_CUSTOM, "value": "X"}})
    assert df["city"].isna().tolist() == [False, True]


# ---------- clean_data (all steps together) ----------

def test_clean_data_runs_every_step_and_reports_counts():
    df = pd.DataFrame({
        "id": [1, 2, 2, 3],
        "name": ["a", "b", "b", ""],
    })
    out, stats = clean_data(
        df,
        remove_duplicates=True,
        fills={"name": {"method": FILL_CUSTOM, "value": "unknown"}},
    )
    assert stats["duplicates_removed"] == 1
    assert stats["cells_filled"] == 1
    assert out["name"].tolist() == ["a", "b", "unknown"]
    assert out.index.tolist() == [0, 1, 2]
    assert len(df) == 4  # original untouched


def test_clean_data_with_no_options_returns_an_equal_copy():
    df = pd.DataFrame({"id": [1, 2], "name": ["a", None]})
    out, stats = clean_data(df)
    assert out.equals(df)
    assert out is not df
    assert stats["duplicates_removed"] == 0
    assert stats["cells_filled"] == 0


def test_clean_data_can_drop_rows_that_are_still_missing():
    df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "", "c"]})
    out, stats = clean_data(df, drop_missing=True)
    assert out["id"].tolist() == [1, 3]
    assert stats["rows_removed_for_missing"] == 1


def test_filling_first_means_fewer_rows_are_dropped():
    df = pd.DataFrame({"id": [1, 2], "name": ["a", ""]})
    out, stats = clean_data(
        df,
        fills={"name": {"method": FILL_CUSTOM, "value": "x"}},
        drop_missing=True,
    )
    assert len(out) == 2
    assert stats["rows_removed_for_missing"] == 0


def test_clean_data_empty_dataframe_does_not_crash():
    df = pd.DataFrame({"id": []})
    out, stats = clean_data(df, remove_duplicates=True, drop_missing=True)
    assert out.empty
    assert stats["duplicates_removed"] == 0