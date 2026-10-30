"""Shared paths and parsing helpers used by the profiling, loading and cleaning scripts."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
CLEAN_DIR = ROOT / "data" / "clean"
REPORTS_DIR = ROOT / "reports"

RAW_TABLES = ["vendors", "items", "purchase_orders", "deliveries", "sales", "inventory"]

DATE_PATTERNS = {  # label -> (regex, strptime format)
    "iso": (r"^\d{4}-\d{2}-\d{2}$", "%Y-%m-%d"),
    "dd/mm/yyyy": (r"^\d{2}/\d{2}/\d{4}$", "%d/%m/%Y"),
    "d-mon-yy": (r"^\d{1,2}-[A-Za-z]{3}-\d{2}$", "%d-%b-%y"),
}


def read_raw(name):
    """Read a raw CSV with every column as text, so nothing is silently converted."""
    return pd.read_csv(RAW_DIR / f"{name}.csv", dtype=str, keep_default_na=False, encoding="utf-8")


def date_format_of(s):
    """Label each value with the date format it is written in: iso, dd/mm/yyyy, d-mon-yy, blank or unknown."""
    s = s.str.strip()
    label = pd.Series("unknown", index=s.index)
    for name, (regex, _) in DATE_PATTERNS.items():
        label[s.str.match(regex)] = name
    label[s == ""] = "blank"
    return label


def parse_mixed_date(s):
    """Parse a column that mixes the three date formats; blanks and unknown formats become NaT."""
    s = s.str.strip()
    fmt = date_format_of(s)
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    for name, (_, pyfmt) in DATE_PATTERNS.items():
        m = fmt == name
        out[m] = pd.to_datetime(s[m], format=pyfmt, errors="coerce")
    return out


def parse_price(s):
    """'₹1,937.23' / '1937.23' / '' -> 1937.23 / 1937.23 / NaN"""
    return pd.to_numeric(s.str.replace("₹", "", regex=False).str.replace(",", "", regex=False).str.strip(),
                         errors="coerce")


def normalize_vendor_name(s):
    """Lower-case and standardise punctuation and legal suffixes so name variants compare equal."""
    s = s.str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
    s = s.str.replace(".", "", regex=False)
    s = s.str.replace("private limited", "pvt ltd", regex=False).str.replace(" limited", " ltd", regex=False)
    return s.str.replace(" and ", " & ", regex=False)


def vendor_core_name(s):
    """Normalised name without the legal suffix (Pvt Ltd / Ltd / LLP / & Co)."""
    return normalize_vendor_name(s).str.replace(r" (pvt ltd|ltd|llp|& co)$", "", regex=True)
