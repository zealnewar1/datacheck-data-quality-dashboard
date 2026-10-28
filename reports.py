"""Day 9: the downloadable issue report. Pure pandas, no Streamlit.

The report describes the ORIGINAL data you uploaded, so every File Row number
matches the row in your file (header = row 1), even after you clean a copy.
"""
from io import BytesIO

import pandas as pd

from quality_summary import flagged_records, quality_summary
from ui_helpers import tidy_numbers


def build_issue_report(df: pd.DataFrame, id_col=None, issues=None) -> dict:
    """Return {sheet name: DataFrame} describing every problem found.

    id_col: the customer-ID column, or None.
    issues: the table returned by run_checks (or None if no rules were run).
    """
    quality = quality_summary(df, id_col, issues)

    summary = pd.DataFrame({
        "Measure": [
            "Total rows",
            "Total columns",
            "Rows with issues",
            "Clean rows",
            "Quality score (%)",
            "Customer ID column",
            "Validation rules",
            "Row numbers",
        ],
        "Value": [
            quality["total_rows"],
            quality["total_columns"],
            quality["rows_with_issues"],
            quality["clean_rows"],
            quality["score"],
            id_col if id_col is not None else "(none)",
            "Applied" if issues is not None else "None selected",
            "File Row = row number in the uploaded file (header = row 1)",
        ],
    })

    sheets = {
        "Summary": summary,
        "Issues by type": quality["table"],
        "Flagged records": tidy_numbers(flagged_records(df, id_col, issues)),
    }
    if issues is not None and not issues.empty:
        sheets["Validation issues"] = issues
    return sheets


def report_to_excel_bytes(sheets: dict) -> bytes:
    """Write each DataFrame to its own sheet and return the .xlsx bytes."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, index=False, sheet_name=name[:31])
    return buffer.getvalue()