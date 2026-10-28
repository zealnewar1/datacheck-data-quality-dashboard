import pandas as pd

from data_quality import duplicate_ids, exact_duplicates, run_checks
from file_loading import load_csv
from quality_summary import quality_summary
from sample_data import COLUMNS, sample_csv_bytes, sample_customers
from ui_helpers import GLOSSARY


def run_sample_checks(df):
    return run_checks(
        df,
        required=["customer_id", "name", "email"],
        email=["email"],
        numeric_range=("age", 0, 120),
    )


def test_sample_has_the_expected_shape():
    df = sample_customers()
    assert df.columns.tolist() == COLUMNS
    assert len(df) == 30


def test_sample_contains_every_kind_of_problem():
    df = sample_customers()
    issues = run_sample_checks(df)
    assert set(issues["Rule"]) >= {"Required field", "Email format", "Number range"}
    assert not exact_duplicates(df).empty
    dup = duplicate_ids(df, "customer_id")
    assert "Same ID, different details" in set(dup["Issue"])
    table = quality_summary(df, "customer_id", issues)["table"]
    assert (table["Issues"] > 0).all()  # every issue type shows up at least once


def test_sample_is_not_perfect_but_not_hopeless():
    df = sample_customers()
    score = quality_summary(df, "customer_id", run_sample_checks(df))["score"]
    assert 40 <= score <= 90


def test_every_issue_type_in_the_sample_has_a_glossary_entry():
    df = sample_customers()
    table = quality_summary(df, "customer_id", run_sample_checks(df))["table"]
    for issue_type in table["Issue type"]:
        assert issue_type in GLOSSARY


def test_sample_csv_loads_back_through_the_real_loader():
    df = load_csv(sample_csv_bytes())
    assert df.columns.tolist() == COLUMNS
    assert len(df) == 30


def test_sample_csv_keeps_ages_as_whole_numbers():
    text = sample_csv_bytes().decode("utf-8-sig")
    assert "28.0" not in text
    assert ",28," in text


def test_sample_is_safe_to_publish():
    df = sample_customers()
    for email in df["email"].dropna():
        if email.strip():
            assert "example" in email  # only made-up example addresses


def test_sample_is_the_same_every_time():
    assert sample_customers().equals(sample_customers())
    assert sample_csv_bytes() == sample_csv_bytes()