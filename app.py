import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO

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
from quality_summary import flagged_records, quality_summary

st.set_page_config(
    page_title="Excel & CSV Data Analyzer",
    page_icon="📊",
    layout="wide",
)

PREVIEW_ROWS = 100


# ---------- Cached helpers ----------
# Streamlit reruns the whole script on every click. Caching means the file is
# parsed once instead of on every widget interaction.

@st.cache_data(show_spinner=False)
def read_csv_bytes(data: bytes) -> pd.DataFrame:
    try:
        return pd.read_csv(BytesIO(data), encoding="utf-8-sig")
    except UnicodeDecodeError:
        # Fallback for CSVs saved in older Windows/Excel encodings
        return pd.read_csv(BytesIO(data), encoding="latin-1")


@st.cache_data(show_spinner=False)
def get_sheet_names(data: bytes) -> list[str]:
    return pd.ExcelFile(BytesIO(data)).sheet_names


@st.cache_data(show_spinner=False)
def read_excel_bytes(data: bytes, sheet: str) -> pd.DataFrame:
    return pd.read_excel(BytesIO(data), sheet_name=sheet)


@st.cache_data(show_spinner=False)
def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Analyzed Data")
    return buffer.getvalue()


def build_chart(df, chart_type, x_col, y_col):
    """Return a Plotly figure, or None if the combination isn't valid."""
    if chart_type == "Histogram":
        return px.histogram(df, x=y_col)

    if chart_type == "Bar Chart":
        if x_col == y_col:
            st.warning("Choose different columns for the X-axis and the numeric column.")
            return None
        chart_df = df.groupby(x_col, dropna=False)[y_col].sum().reset_index()
        return px.bar(chart_df, x=x_col, y=y_col)

    if chart_type == "Line Chart":
        return px.line(df.sort_values(x_col), x=x_col, y=y_col, markers=True)

    return px.scatter(df, x=x_col, y=y_col)


# ---------- Page ----------
st.title("📊 Excel & CSV Data Analyzer")
st.write("Upload your own Excel or CSV file to analyze your data.")

uploaded_file = st.file_uploader(
    "Choose an Excel or CSV file",
    type=["csv", "xlsx"],
)

if uploaded_file is None:
    st.info("👆 Upload a file above to get started.")
    st.subheader("Example data")
    sample_df = pd.DataFrame({
        "Month": ["January", "February", "March"],
        "Sales": [12000, 15000, 11000],
        "Orders": [120, 150, 110],
    })
    st.dataframe(sample_df, width="stretch")
    st.stop()

# ---------- Load data (only file-reading errors are caught here) ----------
file_bytes = uploaded_file.getvalue()

try:
    if uploaded_file.name.lower().endswith(".csv"):
        df = read_csv_bytes(file_bytes)
    else:
        sheet = st.selectbox("Choose worksheet", get_sheet_names(file_bytes))
        df = read_excel_bytes(file_bytes, sheet)
except Exception as error:
    st.error(f"Could not read this file: {error}")
    st.stop()

if df.empty or len(df.columns) == 0:
    st.warning("This file contains no data.")
    st.stop()

# Make every column name a string so charts and selectboxes behave consistently
df = df.rename(columns=str)

# ---------- Overview ----------
st.subheader("📈 Dataset Overview")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Rows", len(df))
c2.metric("Columns", len(df.columns))
c3.metric("Missing cells", int(missing_mask(df).sum().sum()))
c4.metric("Duplicate rows", int(df.duplicated().sum()))

st.subheader("Your Data")
st.dataframe(df.head(PREVIEW_ROWS), width="stretch")

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
    st.dataframe(affected, width="stretch", hide_index=True)

# ---------- Duplicates (Day 5) ----------
st.subheader("👯 Duplicate Records")

st.write("**Exact duplicate rows** (every column is identical)")
exact_dups = exact_duplicates(df)
if exact_dups.empty:
    st.success("No exact duplicate rows found.")
else:
    extra = int((exact_dups["Status"] == "Extra copy").sum())
    d1, d2 = st.columns(2)
    d1.metric("Extra copies to remove", extra)
    d2.metric("Groups of duplicates", int(exact_dups["Duplicate Group"].nunique()))
    st.dataframe(exact_dups, width="stretch", hide_index=True)

st.write("**Duplicate customer IDs** (checked separately)")
id_options = ["(none)"] + df.columns.tolist()
guessed = guess_id_column(df)
id_col = st.selectbox(
    "Which column is the customer ID?",
    id_options,
    index=id_options.index(guessed) if guessed in id_options else 0,
)

if id_col == "(none)":
    st.info("Pick the ID column to check for repeated IDs.")
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
        st.dataframe(dup_ids, width="stretch", hide_index=True)

# ---------- Field validation (Day 6, rule toggles Day 8) ----------
st.subheader("✅ Field Validation")
st.caption("Switch rules on or off, and choose the columns each rule applies to.")

rules = default_rules(df)
all_cols = df.columns.tolist()
numeric_options = ["(none)"] + df.select_dtypes(include="number").columns.tolist()

run_required = st.checkbox("Run the required-fields check", value=True)
required_cols = st.multiselect(
    "Required columns (must not be blank)",
    all_cols,
    default=rules["required"],
    disabled=not run_required,
)

run_email = st.checkbox("Run the email-format check", value=True)
email_cols = st.multiselect(
    "Columns that should contain email addresses",
    all_cols,
    default=rules["email"],
    disabled=not run_email,
)

run_range = st.checkbox("Run the number-range check", value=True)
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
        st.warning("Minimum is larger than maximum, so the range check was skipped.")
    else:
        numeric_range = (range_col, low, high)

# A switched-off rule behaves exactly like a rule with no columns
active_required = required_cols if run_required else []
active_email = email_cols if run_email else []

issues = None  # stays None when no rules are active; the summary below handles that

if not active_required and not active_email and numeric_range is None:
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
        st.info("No records match. Pick at least one issue type.")
    else:
        st.write(f"Showing {len(records)} of {len(df)} rows "
                 "(File Row = row number in your file)")
        st.dataframe(records, width="stretch", hide_index=True)

# ---------- Cleaning ----------
st.subheader("🧹 Clean Your Data")
remove_duplicates = st.checkbox("Remove duplicate rows")
remove_missing = st.checkbox("Remove rows containing missing values")

clean_df = df.copy()
if remove_duplicates:
    clean_df = clean_df.drop_duplicates()
if remove_missing:
    clean_df = clean_df[~missing_mask(clean_df).any(axis=1)]

st.write(f"Original rows: {len(df)} | Rows after cleaning: {len(clean_df)}")

if clean_df.empty:
    st.warning("No rows left after cleaning. Untick an option above.")
    st.stop()

st.dataframe(clean_df.head(PREVIEW_ROWS), width="stretch")

# ---------- Charts ----------
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
        st.error(f"Could not build this chart: {error}")
else:
    st.info("No numeric columns are available for charting.")

# ---------- Downloads ----------
st.subheader("⬇️ Download Your Data")

st.download_button(
    "Download CSV",
    data=clean_df.to_csv(index=False).encode("utf-8-sig"),
    file_name="analyzed_data.csv",
    mime="text/csv",
)

st.download_button(
    "Download Excel",
    data=to_excel_bytes(clean_df),
    file_name="analyzed_data.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.success("Analysis complete!")