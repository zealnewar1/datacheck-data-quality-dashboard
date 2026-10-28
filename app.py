import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO

from cleaning import (
    FILL_CUSTOM,
    FILL_MEAN,
    FILL_MEDIAN,
    FILL_MODE,
    clean_data,
)
from data_quality import (
    default_rules,
    duplicate_ids,
    exact_duplicates,
    guess_id_column,
    missing_mask,
    missing_summary,
    rows_with_missing,
    run_checks,
)
from file_loading import (
    FileLoadError,
    file_kind,
    get_sheet_names,
    load_csv,
    load_excel,
)
from quality_summary import flagged_records, quality_summary
from reports import build_issue_report, report_to_excel_bytes
from sample_data import sample_csv_bytes
from ui_helpers import GLOSSARY, score_message, tidy_numbers

st.set_page_config(
    page_title="Excel & CSV Data Analyzer",
    page_icon="📊",
    layout="wide",
)

PREVIEW_ROWS = 100
SAMPLE_NAME = "sample_customers.csv"


# ---------- Cached helpers ----------
# Streamlit reruns the whole script on every click. Caching means the file is
# parsed once instead of on every widget interaction.

@st.cache_data(show_spinner=False)
def cached_load_csv(data: bytes) -> pd.DataFrame:
    return load_csv(data)


@st.cache_data(show_spinner=False)
def cached_sheet_names(data: bytes) -> list[str]:
    return get_sheet_names(data)


@st.cache_data(show_spinner=False)
def cached_load_excel(data: bytes, sheet: str) -> pd.DataFrame:
    return load_excel(data, sheet)


@st.cache_data(show_spinner=False)
def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Cleaned Data")
    return buffer.getvalue()


def build_chart(df, chart_type, x_col, y_col):
    """Return a Plotly figure, or None if the combination isn't valid."""
    if chart_type == "Histogram":
        return px.histogram(df, x=y_col)

    if chart_type == "Bar Chart":
        if x_col == y_col:
            st.warning("Pick two different columns: one for the bars and one for the numbers.")
            return None
        chart_df = df.groupby(x_col, dropna=False)[y_col].sum().reset_index()
        return px.bar(chart_df, x=x_col, y=y_col)

    if chart_type == "Line Chart":
        return px.line(df.sort_values(x_col), x=x_col, y=y_col, markers=True)

    return px.scatter(df, x=x_col, y=y_col)


def start_sample():
    st.session_state["use_sample"] = True


def stop_sample():
    st.session_state["use_sample"] = False


# ---------- Page ----------
st.title("📊 Excel & CSV Data Analyzer")
st.write(
    "Check a customer spreadsheet for blank cells, duplicates and invalid values. "
    "You get a quality score, a list of the rows to fix, a cleaned copy and a report."
)

no_file_yet = (
    st.session_state.get("upload") is None
    and not st.session_state.get("use_sample", False)
)

with st.expander("How to use this app", expanded=no_file_yet):
    st.markdown(
        "1. **Upload** an Excel (.xlsx) or CSV file, or try the sample data.\n"
        "2. **Read the results.** The app lists blank cells, duplicate rows and invalid "
        "values, and gives a quality score.\n"
        "3. **Clean and download.** Choose how to tidy the data, then download the "
        "cleaned file and the issue report.\n\n"
        "Your original file is never changed, and nothing is stored after you close the page."
    )

with st.expander("What do these terms mean?"):
    for term, meaning in GLOSSARY.items():
        st.markdown(f"**{term}**: {meaning}")

uploaded_file = st.file_uploader(
    "Choose an Excel or CSV file",
    type=["csv", "xlsx"],
    key="upload",
    help="Supported types: .csv and .xlsx. The first row should contain the column headings.",
)

using_sample = st.session_state.get("use_sample", False) and uploaded_file is None

if uploaded_file is None and not using_sample:
    st.info("👆 Upload a file above to get started, or try the sample first.")
    w1, w2 = st.columns(2)
    w1.download_button(
        "⬇️ Download a sample file",
        data=sample_csv_bytes(),
        file_name=SAMPLE_NAME,
        mime="text/csv",
        help="A made-up customer list with deliberate mistakes. Open it in Excel, or upload it here.",
    )
    w2.button(
        "▶️ Try the app with the sample data",
        on_click=start_sample,
        help="Loads the sample file straight away so you can see how everything works.",
    )
    st.stop()

# ---------- Load data (file_loading.py turns every problem into a clear message) ----------
if using_sample:
    st.info(
        "You are looking at the built-in sample data, a made-up customer list with "
        "deliberate mistakes. Upload your own file above at any time."
    )
    st.button("Stop using the sample data", on_click=stop_sample)
    file_name, file_bytes = SAMPLE_NAME, sample_csv_bytes()
else:
    file_name, file_bytes = uploaded_file.name, uploaded_file.getvalue()

try:
    if file_kind(file_name) == "csv":
        df = cached_load_csv(file_bytes)
    else:
        sheet = st.selectbox(
            "Choose worksheet",
            cached_sheet_names(file_bytes),
            help="This Excel file has more than one sheet. Pick the one to analyze.",
        )
        df = cached_load_excel(file_bytes, sheet)
except FileLoadError as error:
    st.error(str(error))
    st.stop()

# ---------- Overview ----------
st.subheader("📈 Dataset Overview")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Rows", len(df))
c2.metric("Columns", len(df.columns))
c3.metric("Blank cells", int(missing_mask(df).sum().sum()))
c4.metric("Duplicate rows", int(df.duplicated().sum()))

st.subheader("Your Data")
st.caption(f"Showing the first {PREVIEW_ROWS} rows." if len(df) > PREVIEW_ROWS else "Showing every row.")
st.dataframe(tidy_numbers(df).head(PREVIEW_ROWS), width="stretch")

with st.expander("View column information"):
    info = pd.DataFrame({
        "Column": df.columns,
        "Data Type": df.dtypes.astype(str).values,
        "Missing Values": missing_mask(df).sum().values,
        "Unique Values": df.nunique().values,
    })
    st.dataframe(info, width="stretch")

# ---------- Missing data (Day 4) ----------
st.subheader("🕳️ Missing Data")
st.caption(GLOSSARY["Missing data"])
summary = missing_summary(df)
affected = rows_with_missing(df)

if affected.empty:
    st.success("No missing values found.")
else:
    m1, m2, m3 = st.columns(3)
    m1.metric("Rows with missing data", len(affected))
    m2.metric("% of all rows", f"{len(affected) / len(df) * 100:.1f}%")
    m3.metric("Columns affected", int((summary["Missing Count"] > 0).sum()))

    st.write("**Missing values per column**")
    st.dataframe(summary, width="stretch", hide_index=True)

    st.write("**Rows that need attention** (File Row = row number in your file)")
    st.dataframe(tidy_numbers(affected), width="stretch", hide_index=True)

# ---------- Duplicates (Day 5) ----------
st.subheader("👯 Duplicate Records")

st.write("**Exact duplicate rows**")
st.caption(GLOSSARY["Exact duplicate rows"])
exact_dups = exact_duplicates(df)
if exact_dups.empty:
    st.success("No exact duplicate rows found.")
else:
    extra = int((exact_dups["Status"] == "Extra copy").sum())
    d1, d2 = st.columns(2)
    d1.metric("Extra copies to remove", extra)
    d2.metric("Groups of duplicates", int(exact_dups["Duplicate Group"].nunique()))
    st.dataframe(tidy_numbers(exact_dups), width="stretch", hide_index=True)

st.write("**Duplicate customer IDs** (checked separately)")
st.caption(GLOSSARY["Duplicate customer IDs (conflicting)"])
id_options = ["(none)"] + df.columns.tolist()
guessed = guess_id_column(df)
id_col = st.selectbox(
    "Which column is the customer ID?",
    id_options,
    index=id_options.index(guessed) if guessed in id_options else 0,
    help="The column that should be unique for every customer. The app guesses it from the column names.",
)

if id_col == "(none)":
    st.info("Pick the ID column above to check for repeated IDs.")
else:
    dup_ids = duplicate_ids(df, id_col)
    if dup_ids.empty:
        st.success(f"Every value in '{id_col}' is unique.")
    else:
        i1, i2 = st.columns(2)
        i1.metric("IDs that repeat", int(dup_ids[id_col].nunique()))
        i2.metric(
            "Conflicting repeats (different details)",
            int(dup_ids.loc[dup_ids["Issue"] == "Same ID, different details", id_col].nunique()),
        )
        st.caption("Blank IDs are reported under Missing Data, not here.")
        st.dataframe(tidy_numbers(dup_ids), width="stretch", hide_index=True)

# ---------- Field validation (Day 6, rule toggles Day 8) ----------
st.subheader("✅ Field Validation")
st.caption(
    "Rules check that the values make sense. Switch each rule on or off, and choose "
    "which columns it applies to."
)

rules = default_rules(df)
all_cols = df.columns.tolist()
numeric_options = ["(none)"] + df.select_dtypes(include="number").columns.tolist()

run_required = st.checkbox(
    "Run the required-fields check",
    value=True,
    help=GLOSSARY["Required field"],
)
required_cols = st.multiselect(
    "Required columns (must not be blank)",
    all_cols,
    default=rules["required"],
    disabled=not run_required,
)

run_email = st.checkbox(
    "Run the email-format check",
    value=True,
    help=GLOSSARY["Email format"],
)
email_cols = st.multiselect(
    "Columns that should contain email addresses",
    all_cols,
    default=rules["email"],
    disabled=not run_email,
)

run_range = st.checkbox(
    "Run the number-range check",
    value=True,
    help=GLOSSARY["Number range"],
)
range_col = st.selectbox(
    "Check that numbers in this column stay within a range",
    numeric_options,
    index=numeric_options.index(rules["range_column"])
    if rules["range_column"] in numeric_options else 0,
    disabled=not run_range,
)

numeric_range = None
if run_range and range_col != "(none)":
    r1, r2 = st.columns(2)
    low = r1.number_input("Minimum allowed", value=rules["range_min"])
    high = r2.number_input("Maximum allowed", value=rules["range_max"])
    if low > high:
        st.warning("The minimum is larger than the maximum, so the range check was skipped.")
    else:
        numeric_range = (range_col, low, high)

# A switched-off rule behaves exactly like a rule with no columns
active_required = required_cols if run_required else []
active_email = email_cols if run_email else []
rules_active = bool(active_required or active_email or numeric_range is not None)

issues = None  # stays None when no rules are active; the summary below handles that

if not rules_active:
    st.info("Switch on at least one rule above to validate your data.")
else:
    issues = run_checks(df, active_required, active_email, numeric_range)
    if issues.empty:
        st.success("All selected checks passed.")
    else:
        v1, v2 = st.columns(2)
        v1.metric("Validation issues", len(issues))
        v2.metric("Rows affected", int(issues["File Row"].nunique()))
        st.write("**Issues by rule**")
        by_rule = issues.groupby(["Rule", "Column"]).size().reset_index(name="Issues")
        st.dataframe(by_rule, width="stretch", hide_index=True)
        st.write("**Every issue** (File Row = row number in your file)")
        st.dataframe(issues, width="stretch", hide_index=True)

# ---------- Quality summary (Day 7) ----------
st.subheader("📋 Quality Summary")
id_arg = None if id_col == "(none)" else id_col
quality = quality_summary(df, id_arg, issues)

q1, q2, q3, q4 = st.columns(4)
q1.metric("Rows", quality["total_rows"])
q2.metric("Columns", quality["total_columns"])
q3.metric("Rows with issues", quality["rows_with_issues"])
q4.metric("Quality score", f"{quality['score']:.1f}%")
st.progress(quality["score"] / 100)

level, message = score_message(quality["score"])
getattr(st, level)(message)

st.write("**Issues by type**")
st.dataframe(quality["table"], width="stretch", hide_index=True)

if quality["rows_with_issues"]:
    st.caption("Rows with issues (File Row numbers): "
               + ", ".join(str(r) for r in quality["flagged_rows"]))

with st.expander("How is the quality score calculated?"):
    st.write(
        "**Score = rows with no issue ÷ total rows × 100.** "
        "A row counts once, however many problems it has. A row is flagged if it "
        "has a blank cell, is an extra copy of an identical row, shares its "
        "customer ID with a row that has different details, or fails one of the "
        "validation rules chosen above."
    )
    if issues is None:
        st.caption("No validation rules are selected, so field validation is not part of this score.")

# ---------- Issues by category (Day 8) ----------
st.subheader("📉 Issues by Category")
issue_table = quality["table"]
chart_data = issue_table[issue_table["Issues"] > 0]

if chart_data.empty:
    st.success("No issues to chart.")
else:
    count_by = st.radio(
        "Count by",
        ["Issues", "Rows affected"],
        horizontal=True,
        help="'Issues' counts every problem. 'Rows affected' counts each row once per type.",
    )
    issues_fig = px.bar(
        chart_data.sort_values(count_by),
        x=count_by,
        y="Issue type",
        orientation="h",
        text=count_by,
    )
    issues_fig.update_layout(yaxis_title=None)
    st.plotly_chart(issues_fig, width="stretch")

# ---------- Records with issues (Day 8) ----------
st.subheader("🔎 Records With Issues")

if chart_data.empty:
    st.success("Every row is clean.")
else:
    only_flagged = st.checkbox("Show only records with issues", value=True)
    available_types = chart_data["Issue type"].tolist()
    chosen_types = st.multiselect(
        "Issue types to show",
        available_types,
        default=available_types,
        disabled=not only_flagged,
    )

    records = flagged_records(
        df, id_arg, issues,
        issue_types=chosen_types, only_flagged=only_flagged,
    )
    if records.empty:
        st.info("No records match. Pick at least one issue type above.")
    else:
        st.write(f"Showing {len(records)} of {len(df)} rows "
                 "(File Row = row number in your file)")
        st.dataframe(tidy_numbers(records), width="stretch", hide_index=True)

# ---------- Clean your data (Day 9) ----------
st.subheader("🧹 Clean Your Data")
st.caption(
    "Your original data is never changed. Cleaning works on a copy, in this order: "
    "remove duplicates, fill blanks, then remove any rows that still have blanks."
)

remove_duplicates = st.checkbox(
    "Remove exact duplicate rows (keeps the first copy)",
    help="Rows with the same ID but different details are NOT removed, because only you can say which is right.",
)

fill_blanks = st.checkbox(
    "Fill selected missing values",
    help="Choose the columns to fill and how. Columns that cannot be filled safely are skipped with a warning.",
)
fills = {}
if fill_blanks:
    blank_mask = missing_mask(df)
    # The ID column is left out: an invented ID or email hides a real problem
    fillable = [c for c in df.columns if blank_mask[c].any() and c != id_arg]
    if not fillable:
        st.info("There are no blank cells to fill (the customer ID column is never filled).")
    else:
        fill_cols = st.multiselect("Columns to fill", fillable)
        for col in fill_cols:
            is_numeric = pd.api.types.is_numeric_dtype(df[col])
            methods = [FILL_MODE, FILL_CUSTOM] + ([FILL_MEDIAN, FILL_MEAN] if is_numeric else [])
            method = st.selectbox(f"How should '{col}' be filled?", methods, key=f"fill_method_{col}")
            value = None
            if method == FILL_CUSTOM:
                value = st.text_input(f"Value to use for '{col}'", key=f"fill_value_{col}")
            fills[col] = {"method": method, "value": value}

remove_missing = st.checkbox(
    "Remove rows that still contain missing values",
    help="Removes any row that still has a blank cell after the steps above.",
)

clean_df, clean_stats = clean_data(df, remove_duplicates, fills, remove_missing)

for col, reason in clean_stats["skipped"]:
    st.warning(f"'{col}' was not filled: {reason}.")

s1, s2, s3, s4, s5 = st.columns(5)
s1.metric("Original rows", len(df))
s2.metric("Rows after cleaning", len(clean_df))
s3.metric("Duplicates removed", clean_stats["duplicates_removed"])
s4.metric("Cells filled", clean_stats["cells_filled"])
s5.metric("Rows removed (blanks)", clean_stats["rows_removed_for_missing"])

has_rows = not clean_df.empty

if not has_rows:
    st.warning("No rows are left after cleaning. Untick one of the options above.")
else:
    issues_after = (
        run_checks(clean_df, active_required, active_email, numeric_range)
        if rules_active else None
    )
    after = quality_summary(clean_df, id_arg, issues_after)
    st.metric(
        "Quality score after cleaning",
        f"{after['score']:.1f}%",
        delta=f"{after['score'] - quality['score']:+.1f} points vs. original",
    )
    st.dataframe(tidy_numbers(clean_df).head(PREVIEW_ROWS), width="stretch")

# ---------- Charts ----------
if has_rows:
    st.subheader("📊 Visualize Your Data")
    numeric_cols = clean_df.select_dtypes(include="number").columns.tolist()

    if numeric_cols:
        chart_type = st.selectbox(
            "Chart type",
            ["Bar Chart", "Line Chart", "Scatter Plot", "Histogram"],
        )
        y_col = st.selectbox("Choose numeric column", numeric_cols)

        # A histogram only needs one column, so hide the X-axis picker for it
        x_col = None
        if chart_type != "Histogram":
            x_col = st.selectbox("Choose category or X-axis", clean_df.columns.tolist())

        try:
            fig = build_chart(clean_df, chart_type, x_col, y_col)
            if fig is not None:
                st.plotly_chart(fig, width="stretch")
        except Exception as error:
            st.error("This chart could not be drawn with the columns you picked. Try a different combination.")
            st.caption(f"Technical detail: {error}")
    else:
        st.info("This data has no numeric columns, so there is nothing to chart.")

# ---------- Downloads (Day 9) ----------
st.subheader("⬇️ Download")
st.caption(
    "The issue report describes your original file, so its File Row numbers "
    "match the rows you uploaded."
)

report_bytes = report_to_excel_bytes(build_issue_report(df, id_arg, issues))
xlsx_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

dl1, dl2, dl3 = st.columns(3)
if has_rows:
    download_df = tidy_numbers(clean_df)
    dl1.download_button(
        "Cleaned data (CSV)",
        data=download_df.to_csv(index=False).encode("utf-8-sig"),
        file_name="cleaned_data.csv",
        mime="text/csv",
    )
    dl2.download_button(
        "Cleaned data (Excel)",
        data=to_excel_bytes(download_df),
        file_name="cleaned_data.xlsx",
        mime=xlsx_mime,
    )
else:
    dl1.info("Nothing to download: no rows are left after cleaning.")

dl3.download_button(
    "Issue report (Excel)",
    data=report_bytes,
    file_name="issue_report.xlsx",
    mime=xlsx_mime,
)

st.success("Analysis complete!")