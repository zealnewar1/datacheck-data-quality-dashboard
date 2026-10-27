"""Data-quality checks. Pure pandas functions: no Streamlit, so they are easy to test."""
import pandas as pd


def missing_mask(df: pd.DataFrame) -> pd.DataFrame:
    """True where a cell is missing.

    A cell counts as missing if it is NaN/None OR a text cell that is empty
    or contains only spaces (pandas does not treat "   " as NaN by itself).
    """
    mask = df.isna()
    for col in df.columns:
        if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
            blank = df[col].astype("string").str.strip().eq("").fillna(False).astype(bool)
            mask[col] = mask[col] | blank
    return mask


def missing_summary(df: pd.DataFrame) -> pd.DataFrame:
    """One row per column: how many cells are missing and what percent of rows."""
    counts = missing_mask(df).sum()
    total_rows = len(df)
    percent = (counts / total_rows * 100).round(1) if total_rows else counts * 0.0
    summary = pd.DataFrame({
        "Column": counts.index,
        "Missing Count": counts.values,
        "Missing %": percent.values,
    })
    return summary.sort_values("Missing Count", ascending=False).reset_index(drop=True)


def rows_with_missing(df: pd.DataFrame) -> pd.DataFrame:
    """Rows that have at least one missing cell, with a note of which columns.

    'File Row' is the row number as you would see it in Excel/CSV
    (header is row 1, so the first data row is row 2).
    """
    mask = missing_mask(df)
    has_missing = mask.any(axis=1)
    if not has_missing.any():
        return pd.DataFrame(columns=["File Row", "Missing In", *df.columns])

    affected = df[has_missing].copy()
    affected.insert(0, "Missing In", [
        ", ".join(mask.columns[row]) for row in mask[has_missing].to_numpy()
    ])
    affected.insert(0, "File Row", affected.index + 2)
    return affected


# ---------- Day 5: duplicates ----------

def guess_id_column(df: pd.DataFrame):
    """Return the first column that looks like an ID column, or None."""
    for col in df.columns:
        name = str(col).strip().lower().replace(" ", "_")
        if name in ("id", "customerid", "cust_id") or name.endswith("_id"):
            return col
    return None


def exact_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Every row that has an identical twin (all columns equal).

    'Duplicate Group' puts identical rows under the same number.
    'Status' tells you which one is the original and which are extra copies.
    """
    in_group = df.duplicated(keep=False)
    if not in_group.any():
        return pd.DataFrame(columns=["File Row", "Duplicate Group", "Status", *df.columns])

    result = df[in_group].copy()
    extra_copy = df.duplicated(keep="first")[in_group]
    groups = result.groupby(list(df.columns), dropna=False, sort=False).ngroup() + 1

    result.insert(0, "Status", extra_copy.map({True: "Extra copy", False: "First copy"}))
    result.insert(0, "Duplicate Group", groups)
    result.insert(0, "File Row", result.index + 2)
    return result


def duplicate_ids(df: pd.DataFrame, id_col) -> pd.DataFrame:
    """Rows whose ID appears more than once, labelled by what kind of repeat.

    Blank IDs are NOT counted here: a blank ID is a missing-data problem,
    and two blanks are not 'the same ID'.
    """
    blank = missing_mask(df)[id_col]
    shared = df[id_col].duplicated(keep=False) & ~blank
    if not shared.any():
        return pd.DataFrame(columns=["File Row", "Issue", *df.columns])

    identical = df.duplicated(keep=False)[shared]
    result = df[shared].copy().sort_values(id_col, kind="stable")
    result.insert(0, "Issue", identical.loc[result.index].map({
        True: "Same ID, identical row",
        False: "Same ID, different details",
    }))
    result.insert(0, "File Row", result.index + 2)
    return result