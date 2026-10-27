"""Data-quality checks. Pure pandas functions: no Streamlit, so they are easy to test."""
import re

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


# ---------- Day 6: field validation ----------
# Every check returns issues in the SAME long format (one row per problem),
# so later days can count, chart, filter and export them all the same way.

ISSUE_COLUMNS = ["File Row", "Rule", "Column", "Value", "Problem"]

# something@domain.tld : no spaces, exactly one @, a dot in the domain,
# and no empty parts such as "a@b..com" or "@example.com"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")


def _empty_issues() -> pd.DataFrame:
    return pd.DataFrame(columns=ISSUE_COLUMNS)


def _issue_rows(df, mask, rule, column, problem) -> pd.DataFrame:
    """Turn a True/False row mask into issue rows."""
    rows = df[mask]
    shown = rows[column].astype("string").fillna("")
    shown = shown.where(shown.str.strip() != "", "(blank)")
    return pd.DataFrame({
        "File Row": (rows.index + 2).to_numpy(),
        "Rule": rule,
        "Column": column,
        "Value": shown.to_numpy(),
        "Problem": problem,
    })


def _combine(parts) -> pd.DataFrame:
    parts = [p for p in parts if not p.empty]
    if not parts:
        return _empty_issues()
    combined = pd.concat(parts, ignore_index=True)
    return combined.sort_values(["File Row", "Rule"], kind="stable").reset_index(drop=True)


def check_required(df: pd.DataFrame, columns) -> pd.DataFrame:
    """Required columns must not be blank. Also covers empty customer IDs."""
    mask = missing_mask(df)
    parts = [
        _issue_rows(df, mask[c], "Required field", c, "Required value is blank")
        for c in columns if c in df.columns
    ]
    return _combine(parts)


def check_email(df: pd.DataFrame, column) -> pd.DataFrame:
    """Non-blank values that are not valid email addresses.

    Blank cells are skipped here: they are reported by the required-field
    rule (or the missing-data section), not counted twice as 'invalid'.
    """
    if column not in df.columns:
        return _empty_issues()
    blank = missing_mask(df)[column]
    valid = df[column].astype("string").str.match(EMAIL_PATTERN).fillna(False).astype(bool)
    return _issue_rows(
        df, ~blank & ~valid, "Email format", column,
        "Not a valid email (check the @, the domain and spaces)",
    )


def check_range(df: pd.DataFrame, column, min_value, max_value) -> pd.DataFrame:
    """Numbers must lie between min_value and max_value (inclusive)."""
    if column not in df.columns:
        return _empty_issues()
    blank = missing_mask(df)[column]
    numbers = pd.to_numeric(df[column], errors="coerce")
    not_a_number = ~blank & numbers.isna()
    outside = numbers.notna() & ((numbers < min_value) | (numbers > max_value))
    return _combine([
        _issue_rows(df, not_a_number, "Number range", column, "Not a number"),
        _issue_rows(df, outside, "Number range", column,
                    f"Outside allowed range {min_value:g} to {max_value:g}"),
    ])


def default_rules(df: pd.DataFrame) -> dict:
    """Sensible starting rules, built only from columns that exist in this file."""
    cols = list(df.columns)
    id_col = guess_id_column(df)
    return {
        "required": [c for c in cols if c == id_col or str(c).strip().lower() in ("name", "email")],
        "email": [c for c in cols if "mail" in str(c).lower()],
        "range_column": next((c for c in cols if str(c).strip().lower() == "age"), None),
        "range_min": 0.0,
        "range_max": 120.0,
    }


def run_checks(df: pd.DataFrame, required=(), email=(), numeric_range=None) -> pd.DataFrame:
    """Run the chosen rules. Columns that are not in the file are ignored.

    numeric_range is None or a tuple: (column, min_value, max_value).
    """
    parts = [check_required(df, list(required))]
    parts += [check_email(df, c) for c in email]
    if numeric_range is not None:
        column, low, high = numeric_range
        parts.append(check_range(df, column, low, high))
    return _combine(parts)