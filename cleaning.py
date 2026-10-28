"""Day 9: safe cleaning helpers. Pure pandas, no Streamlit.

Every function returns a NEW DataFrame. The data you pass in is never changed,
so the original upload always stays intact.

Cleaning order used by clean_data():
  1. remove exact duplicate rows (the first copy is kept)
  2. fill chosen missing values
  3. remove rows that still contain a missing value

"Missing" means exactly what the rest of the app means by it (missing_mask),
so blank text cells count as missing, not just empty cells.
"""
import pandas as pd

from data_quality import exact_duplicates, missing_mask

FILL_CUSTOM = "Custom value"
FILL_MODE = "Most common value"
FILL_MEDIAN = "Median (numbers only)"
FILL_MEAN = "Mean (numbers only)"


def remove_exact_duplicates(df: pd.DataFrame):
    """Drop extra copies of identical rows, keeping the first copy.

    Rows that share an ID but differ in other columns are NOT removed: we
    cannot tell which version is right, so a person has to decide.
    Expects the normal 0..n-1 index of a freshly loaded file.
    Returns (new_df, number_of_rows_removed).
    """
    dups = exact_duplicates(df)
    extra_rows = dups.loc[dups["Status"] == "Extra copy", "File Row"]
    labels = [int(r) - 2 for r in extra_rows]  # File Row = index + 2
    return df.drop(index=labels), len(labels)


def remove_rows_with_missing(df: pd.DataFrame):
    """Drop every row that has at least one missing cell.

    Returns (new_df, number_of_rows_removed).
    """
    bad = missing_mask(df).any(axis=1)
    return df[~bad], int(bad.sum())


def fill_missing(df: pd.DataFrame, fills: dict):
    """Fill missing cells column by column.

    fills: {column: {"method": FILL_*, "value": text}}. "value" is only used
    by FILL_CUSTOM. Columns that cannot be filled safely are skipped, never
    guessed at.
    Returns (new_df, cells_filled, skipped) where skipped is a list of
    (column, reason).
    """
    out = df.copy()
    mask = missing_mask(out)
    cells_filled = 0
    skipped = []

    for col, spec in fills.items():
        if col not in out.columns:
            skipped.append((col, "Column not found"))
            continue

        rows = mask[col]
        count = int(rows.sum())
        if count == 0:
            continue  # nothing to fill

        method = spec.get("method")
        present = out.loc[~rows, col]
        numeric = pd.api.types.is_numeric_dtype(out[col])

        try:
            if method == FILL_CUSTOM:
                raw = spec.get("value")
                if raw is None or str(raw).strip() == "":
                    skipped.append((col, "No value was entered"))
                    continue
                value = raw
                if numeric:
                    value = pd.to_numeric(raw, errors="coerce")
                    if pd.isna(value):
                        skipped.append((col, f"'{raw}' is not a number"))
                        continue
            elif method == FILL_MODE:
                if present.empty:
                    skipped.append((col, "Every value is missing, so there is nothing to copy"))
                    continue
                value = present.mode().iloc[0]
            elif method in (FILL_MEDIAN, FILL_MEAN):
                if not numeric:
                    skipped.append((col, "Not a numeric column"))
                    continue
                if present.empty:
                    skipped.append((col, "Every value is missing, so there is nothing to average"))
                    continue
                value = present.median() if method == FILL_MEDIAN else present.mean()
            else:
                skipped.append((col, "Unknown fill method"))
                continue

            out.loc[rows, col] = value
            cells_filled += count
        except Exception:
            skipped.append((col, "Could not fill this column"))

    return out, cells_filled, skipped


def clean_data(df: pd.DataFrame, remove_duplicates=False, fills=None,
               drop_missing=False):
    """Apply the chosen cleaning steps to a copy of df.

    Returns (cleaned_df, stats). The cleaned frame has a fresh 0..n-1 index.
    stats has: duplicates_removed, cells_filled, rows_removed_for_missing,
    skipped.
    """
    out = df.copy()
    stats = {
        "duplicates_removed": 0,
        "cells_filled": 0,
        "rows_removed_for_missing": 0,
        "skipped": [],
    }

    if remove_duplicates:
        out, stats["duplicates_removed"] = remove_exact_duplicates(out)
    if fills:
        out, stats["cells_filled"], stats["skipped"] = fill_missing(out, fills)
    if drop_missing:
        out, stats["rows_removed_for_missing"] = remove_rows_with_missing(out)

    return out.reset_index(drop=True), stats