"""Day 11: small helpers that make the app easier to read. No Streamlit.

- tidy_numbers: show whole numbers as 25 instead of 25.0
- score_message: a plain-English verdict for the quality score
- GLOSSARY: one-line explanations of every term the app uses
"""
import numpy as np
import pandas as pd

# Keys for issue types must match the names used in quality_summary / run_checks.
GLOSSARY = {
    "Missing data": (
        "A blank cell: nothing typed in it, or only spaces. Each blank cell is a gap in your data."
    ),
    "Exact duplicate rows": (
        "Two or more rows that are identical in every column. Usually the same record entered twice."
    ),
    "Duplicate customer IDs (conflicting)": (
        "The same customer ID appears on more than one row, but the other details differ "
        "(for example two different emails). The app cannot tell which row is correct, so it flags both."
    ),
    "Required field": (
        "A column you marked as must-have, such as the customer ID or name, that is blank on some rows."
    ),
    "Email format": (
        "An email address that does not look right: no @, two @ signs, spaces, or no domain like .com."
    ),
    "Number range": (
        "A number outside the limits you set, for example an age of -3 or 142."
    ),
    "File Row": (
        "The row number in your original file, counting the heading row as row 1. "
        "Use it to find the problem in Excel."
    ),
    "Quality score": (
        "The percentage of rows with no problems. A row counts once, however many problems it has."
    ),
}


def score_message(score: float):
    """Return (streamlit level, plain-English message) for a 0-100 quality score."""
    if score >= 90:
        return "success", f"Looking good: {score:.1f}% of your rows have no problems."
    if score >= 70:
        return "warning", (
            f"Some cleaning needed: {score:.1f}% of your rows have no problems. "
            "Check the sections below to see what to fix."
        )
    return "error", (
        f"Needs attention: only {score:.1f}% of your rows have no problems. "
        "Start with the Records With Issues section below."
    )


def tidy_numbers(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy where decimal columns holding only whole numbers become integers.

    pandas turns a whole-number column into decimals (25.0) when it has a blank
    cell. This turns it back for display and downloads. Blanks stay blank.
    Only use the result for showing or saving data, not for analysis.
    """
    out = df.copy()
    for i in range(out.shape[1]):
        column = out.iloc[:, i]
        if not pd.api.types.is_float_dtype(column):
            continue
        present = column.dropna()
        if present.empty or not np.isfinite(present).all():
            continue
        if (present == present.round()).all():
            out.isetitem(i, column.astype("Int64"))
    return out