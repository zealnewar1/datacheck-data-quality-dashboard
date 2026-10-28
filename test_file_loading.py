from io import BytesIO

import pandas as pd
import pytest

from file_loading import (
    FileLoadError,
    file_kind,
    get_sheet_names,
    load_csv,
    load_excel,
)


def excel_bytes(sheets: dict) -> bytes:
    """Build a real .xlsx file in memory: {sheet name: DataFrame}."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, index=False, sheet_name=name)
    return buffer.getvalue()


# ---------- File type ----------

def test_file_kind_recognises_csv_and_xlsx_in_any_case():
    assert file_kind("customers.csv") == "csv"
    assert file_kind("DATA.XLSX") == "xlsx"


@pytest.mark.parametrize("name", ["notes.txt", "old.xls", "report.pdf", "archive.csv.zip"])
def test_unsupported_file_types_are_rejected(name):
    with pytest.raises(FileLoadError, match="not supported"):
        file_kind(name)


def test_file_without_extension_is_rejected():
    with pytest.raises(FileLoadError, match="no extension"):
        file_kind("customers")


def test_missing_file_name_is_rejected():
    with pytest.raises(FileLoadError):
        file_kind(None)


# ---------- CSV ----------

def test_valid_csv_loads():
    df = load_csv(b"id,name\n1,Asha\n2,Ben\n")
    assert df["name"].tolist() == ["Asha", "Ben"]
    assert len(df) == 2


def test_csv_saved_by_excel_with_bom_has_clean_column_names():
    df = load_csv(b"\xef\xbb\xbfid,name\n1,Asha\n")
    assert df.columns.tolist() == ["id", "name"]


def test_csv_in_old_windows_encoding_is_still_read():
    df = load_csv("name\nJos\u00e9\n".encode("latin-1"))
    assert df["name"].tolist() == ["Jos\u00e9"]


def test_numeric_column_names_become_text():
    df = load_csv(b"1,2\n3,4\n")
    assert df.columns.tolist() == ["1", "2"]


def test_empty_csv_is_rejected():
    with pytest.raises(FileLoadError, match="empty"):
        load_csv(b"")


def test_csv_with_only_blank_space_is_rejected():
    with pytest.raises(FileLoadError, match="empty"):
        load_csv(b"  \n\n  \n")


def test_csv_with_headings_but_no_rows_is_rejected():
    with pytest.raises(FileLoadError, match="no data rows"):
        load_csv(b"id,name,email\n")


def test_csv_with_uneven_rows_is_rejected_with_a_helpful_message():
    with pytest.raises(FileLoadError, match="different number of columns"):
        load_csv(b"a,b\n1,2\n3,4,5,6\n")


def test_binary_junk_is_not_accepted_as_data():
    with pytest.raises(FileLoadError):
        load_csv(b"\x00\x01\x02\x03")


# ---------- Excel ----------

def test_valid_excel_loads_and_lists_its_sheets():
    data = excel_bytes({
        "Customers": pd.DataFrame({"id": [1, 2], "name": ["Asha", "Ben"]}),
        "Other": pd.DataFrame({"x": [1]}),
    })
    assert get_sheet_names(data) == ["Customers", "Other"]
    df = load_excel(data, "Customers")
    assert df["name"].tolist() == ["Asha", "Ben"]


def test_each_worksheet_is_read_separately():
    data = excel_bytes({
        "A": pd.DataFrame({"x": [1]}),
        "B": pd.DataFrame({"y": [2]}),
    })
    assert load_excel(data, "B").columns.tolist() == ["y"]


def test_empty_excel_bytes_are_rejected():
    with pytest.raises(FileLoadError, match="empty"):
        get_sheet_names(b"")
    with pytest.raises(FileLoadError, match="empty"):
        load_excel(b"", "Sheet1")


def test_damaged_excel_file_is_rejected():
    with pytest.raises(FileLoadError, match="could not be opened"):
        get_sheet_names(b"this is not really an excel file")


def test_excel_loading_a_damaged_file_is_rejected():
    with pytest.raises(FileLoadError):
        load_excel(b"this is not really an excel file", "Sheet1")


def test_unknown_worksheet_name_is_rejected():
    data = excel_bytes({"Customers": pd.DataFrame({"id": [1]})})
    with pytest.raises(FileLoadError, match="Missing"):
        load_excel(data, "Missing")


def test_blank_worksheet_is_rejected():
    data = excel_bytes({"Blank": pd.DataFrame()})
    with pytest.raises(FileLoadError):
        load_excel(data, "Blank")


def test_worksheet_with_headings_only_is_rejected():
    data = excel_bytes({"Headers": pd.DataFrame({"id": [], "name": []})})
    with pytest.raises(FileLoadError, match="no data rows"):
        load_excel(data, "Headers")