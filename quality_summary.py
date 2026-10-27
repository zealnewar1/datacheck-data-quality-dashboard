"""Day 7: quality summary and score. Pure pandas, no Streamlit.

Quality score = (rows with no issue / total rows) x 100

A row is "flagged" if ANY of these apply, and it counts only once however
many problems it has:
  - it has a missing (blank) cell
  - it is an extra copy of an identical row (the first copy is not flagged)
  - it shares a customer ID with a row that has different details
    (both rows are flagged, because we cannot tell which one is right)
  - it has a field-validation issue (required, email format, number range)
"""
import pandas as pd

from data_quality import duplicate_ids, exact_duplicates, missing_mask

TABLE_COLUMNS = ["Issue type", "Issues", "Rows affected"]


def _as_row_set(values) -> set:
    return {int(v) for v in values}


def quality_summary(df: pd.DataFrame, id_col=None, issues=None) -> dict:
    """Count every issue type and calculate the quality score.

    id_col: the customer-ID column, or None to skip the duplicate-ID check.
    issues: the table returned by run_checks (or None if no rules were chosen).
    All row numbers are 'File Row' numbers (header = row 1).
    """
    total_rows = len(df)
    entries = []  # (issue type, number of issues, set of file rows)

    # Missing data: issues = blank cells, rows = rows containing any blank
    mask = missing_mask(df)
    missing_rows = _as_row_set(df.index[mask.any(axis=1)] + 2)
    entries.append(("Missing data", int(mask.sum().sum()), missing_rows))

    # Exact duplicates: only the extra copies are flagged
    dups = exact_duplicates(df)
    extra_rows = _as_row_set(dups.loc[dups["Status"] == "Extra copy", "File Row"])
    entries.append(("Exact duplicate rows", len(extra_rows), extra_rows))

    # Duplicate IDs with conflicting details
    conflict_rows = set()
    if id_col is not None and id_col in df.columns:
        dup_ids = duplicate_ids(df, id_col)
        conflict_rows = _as_row_set(
            dup_ids.loc[dup_ids["Issue"] == "Same ID, different details", "File Row"]
        )
    entries.append(("Duplicate customer IDs (conflicting)", len(conflict_rows), conflict_rows))

    # Field validation, one entry per rule that found something
    if issues is not None and not issues.empty:
        for rule, group in issues.groupby("Rule", sort=True):
            entries.append((rule, len(group), _as_row_set(group["File Row"])))

    flagged = set()
    for _, _, rows in entries:
        flagged |= rows

    if total_rows == 0:
        score = 100.0
    else:
        score = round((total_rows - len(flagged)) / total_rows * 100, 1)

    table = pd.DataFrame(
        [(name, count, len(rows)) for name, count, rows in entries],
        columns=TABLE_COLUMNS,
    )
    return {
        "total_rows": total_rows,
        "total_columns": len(df.columns),
        "rows_with_issues": len(flagged),
        "clean_rows": total_rows - len(flagged),
        "score": score,
        "table": table,
        "flagged_rows": sorted(flagged),
    }