"""Day 11: a built-in sample file with deliberate problems. No Streamlit.

Everything here is made up. Names and emails are fictional, and every email
uses example.com, so the file is safe to publish.
"""
import pandas as pd

COLUMNS = ["customer_id", "name", "email", "age", "city"]

_ROWS = [
    ("C001", "Asha Verma", "asha.verma@example.com", 28, "Pune"),
    ("C002", "Ben Carter", "ben.carter@example.com", 34, "Jaipur"),
    ("C003", "Chitra Nair", "chitra.nair@example.com", 41, "Kochi"),
    ("C004", "Daniel Foster", "daniel.foster@example.com", 26, "Nagpur"),
    ("C005", "Esha Menon", "esha.menon.example.com", 31, "Surat"),         # email has no @
    ("C006", "Farid Khan", "farid.khan@example.com", 45, "Pune"),
    ("C007", "Grace Lobo", "grace.lobo@example.com", 29, "Jaipur"),
    ("C008", "Hari Prasad", "", 38, "Kochi"),                              # blank email
    ("C009", "Isha Kapoor", "isha.kapoor@example.com", None, "Nagpur"),    # blank age
    ("C010", "Jon Mathew", "jon.mathew@example.com", 52, "Surat"),
    ("C011", "Kavya Reddy", "kavya.reddy@example.com", 33, "Pune"),
    ("C012", "Liam Brooks", "liam.brooks@example.com", 27, "Jaipur"),
    ("C013", "", "mira.joshi@example.com", 36, "Kochi"),                   # blank name
    ("C014", "Nikhil Rao", "nikhil.rao@example.com", -3, "Nagpur"),        # age below range
    ("C015", "Olivia Grant", "olivia.grant@example.com", 30, "Surat"),
    ("C016", "Pranav Shah", "pranav.shah@@example.com", 44, "Pune"),       # two @ signs
    ("C017", "Quinn Davis", "quinn.davis@example.com", 39, "Jaipur"),
    ("C018", "Riya Sen", "riya.sen@example", 25, "Kochi"),                 # no .com
    ("C019", "Sam Wilson", "sam wilson@example.com", 48, "Nagpur"),        # space in email
    ("C020", "Tara Pillai", "tara.pillai@example.com", 32, "Surat"),
    ("C021", "Uma Iyer", "uma.iyer@example.com", 142, "Pune"),             # age above range
    ("C022", "Victor Hall", "victor.hall@example.com", 37, "Jaipur"),
    ("C023", "Wendy Clark", "wendy.clark@example.com", 29, "Kochi"),
    ("C024", "Xavier D'Souza", "xavier.dsouza@example.com", 43, "Nagpur"),
    ("C025", "Yara Ali", "yara.ali@example.com", 35, "Surat"),
    ("C026", "Zane Parker", "zane.parker@example.com", 40, "Pune"),
    ("C012", "Liam Brooks", "liam.brooks@example.com", 27, "Jaipur"),     # exact duplicate of C012
    ("C020", "Tara Pillai", "tara.new@example.com", 32, "Surat"),          # same ID, different email
    ("", "Alex Morgan", "alex.morgan@example.com", 31, "Jaipur"),          # blank customer ID
    ("C030", "Nina Patel", "@example.com", 27, "Kochi"),                   # email has no name part
]


def sample_customers() -> pd.DataFrame:
    """The sample table, with ages kept as whole numbers."""
    df = pd.DataFrame(_ROWS, columns=COLUMNS)
    df["age"] = df["age"].astype("Int64")
    return df


def sample_csv_bytes() -> bytes:
    """The sample as CSV bytes, ready for a download button (opens cleanly in Excel)."""
    return sample_customers().to_csv(index=False).encode("utf-8-sig")