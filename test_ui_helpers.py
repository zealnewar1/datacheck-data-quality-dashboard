import numpy as np
import pandas as pd
import pytest

from ui_helpers import GLOSSARY, score_message, tidy_numbers


# ---------- tidy_numbers ----------

def test_whole_number_decimals_become_integers():
    df = pd.DataFrame({"age": [25.0, 30.0, 41.0]})
    out = tidy_numbers(df)
    assert out["age"].tolist() == [25, 30, 41]
    assert str(out["age"].dtype) == "Int64"


def test_blanks_stay_blank_when_a_column_is_tidied():
    df = pd.DataFrame({"age": [25.0, None, 41.0]})
    out = tidy_numbers(df)
    assert out["age"].isna().tolist() == [False, True, False]
    assert out["age"].dropna().tolist() == [25, 41]


def test_real_decimals_are_left_alone():
    df = pd.DataFrame({"score": [1.5, 2.0, 3.25]})
    assert tidy_numbers(df)["score"].tolist() == [1.5, 2.0, 3.25]


def test_text_and_integer_columns_are_untouched():
    df = pd.DataFrame({"name": ["a", "b"], "id": [1, 2]})
    out = tidy_numbers(df)
    assert out.equals(df)


def test_all_blank_numeric_column_is_untouched():
    df = pd.DataFrame({"x": pd.Series([None, None], dtype=float)})
    assert tidy_numbers(df)["x"].isna().all()
    assert str(tidy_numbers(df)["x"].dtype) == "float64"


def test_infinite_values_are_left_alone():
    df = pd.DataFrame({"x": [1.0, np.inf]})
    assert str(tidy_numbers(df)["x"].dtype) == "float64"


def test_original_is_not_changed():
    df = pd.DataFrame({"age": [25.0, None]})
    tidy_numbers(df)
    assert str(df["age"].dtype) == "float64"


def test_empty_dataframe_does_not_crash():
    assert tidy_numbers(pd.DataFrame({"age": pd.Series([], dtype=float)})).empty


def test_duplicate_column_names_do_not_crash():
    df = pd.DataFrame([[1.0, 2.5]], columns=["x", "x"])
    out = tidy_numbers(df)
    assert out.iloc[0, 0] == 1 and out.iloc[0, 1] == 2.5


def test_csv_output_has_no_decimal_point_for_whole_numbers():
    df = pd.DataFrame({"age": [25.0, None, 41.0]})
    text = tidy_numbers(df).to_csv(index=False)
    assert "25.0" not in text and "25" in text


# ---------- score_message ----------

@pytest.mark.parametrize("score, level", [
    (100.0, "success"), (90.0, "success"),
    (89.9, "warning"), (70.0, "warning"),
    (69.9, "error"), (0.0, "error"),
])
def test_score_message_levels(score, level):
    assert score_message(score)[0] == level


def test_score_message_mentions_the_score():
    assert "60.0%" in score_message(60.0)[1]


# ---------- glossary ----------

def test_glossary_entries_are_all_non_empty_sentences():
    for term, text in GLOSSARY.items():
        assert term.strip() and len(text) > 20