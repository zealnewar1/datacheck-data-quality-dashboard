"""Day 10: reading uploaded files. Pure pandas, no Streamlit.

Every problem with an uploaded file is raised as FileLoadError, with a message
written for a non-technical user. The app only has to catch that one error, and
tests can check each bad-file case without starting Streamlit.
"""
import os
from io import BytesIO

import pandas as pd


class FileLoadError(Exception):
    """A problem with the uploaded file, worded so a non-technical user can act on it."""


def file_kind(filename) -> str:
    """Return 'csv' or 'xlsx' from the file name, or raise FileLoadError."""
    name = (filename or "").lower()
    if name.endswith(".csv"):
        return "csv"
    if name.endswith(".xlsx"):
        return "xlsx"
    ext = os.path.splitext(name)[1]
    what = f"The file type '{ext}'" if ext else "A file with no extension"
    raise FileLoadError(f"{what} is not supported. Please upload a .csv or .xlsx file.")


def _check_not_empty(data: bytes) -> None:
    if not data or not data.strip():
        raise FileLoadError("This file is empty. Please upload a file that contains data.")


def _finish(df: pd.DataFrame) -> pd.DataFrame:
    """Reject tables with nothing to analyze; make every column name a string."""
    if len(df.columns) == 0:
        raise FileLoadError("This file has no columns, so there is nothing to analyze.")
    if df.empty:
        raise FileLoadError("This file has column headings but no data rows.")
    return df.rename(columns=str)


def load_csv(data: bytes) -> pd.DataFrame:
    """Read CSV bytes into a DataFrame (UTF-8 first, then older Windows encodings)."""
    _check_not_empty(data)
    try:
        try:
            df = pd.read_csv(BytesIO(data), encoding="utf-8-sig")
        except UnicodeDecodeError:
            df = pd.read_csv(BytesIO(data), encoding="latin-1")
    except pd.errors.EmptyDataError:
        raise FileLoadError("This file has no readable data.") from None
    except pd.errors.ParserError:
        raise FileLoadError(
            "This CSV file could not be read. Some rows seem to have a different "
            "number of columns than the heading row."
        ) from None
    except Exception:
        raise FileLoadError("This CSV file could not be read. It may be damaged.") from None
    return _finish(df)


def get_sheet_names(data: bytes) -> list:
    """List the worksheets in an .xlsx file."""
    _check_not_empty(data)
    try:
        return pd.ExcelFile(BytesIO(data)).sheet_names
    except Exception:
        raise FileLoadError(
            "This Excel file could not be opened. It may be damaged, or it may "
            "not really be an .xlsx file."
        ) from None


def load_excel(data: bytes, sheet) -> pd.DataFrame:
    """Read one worksheet of an .xlsx file into a DataFrame."""
    _check_not_empty(data)
    try:
        df = pd.read_excel(BytesIO(data), sheet_name=sheet)
    except Exception:
        raise FileLoadError(
            f"The worksheet '{sheet}' could not be read. The file may be damaged."
        ) from None
    return _finish(df)