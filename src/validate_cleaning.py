"""
Phase 3, step 3: score the cleaned data against the ground truth in data/truth/.

The ground truth is never used by the cleaning itself; this script only measures how close
the cleaned tables came to the true values. Writes reports/cleaning_validation.md.

Run from the project root (after src/clean_data.py):
    .venv/Scripts/python src/validate_cleaning.py
"""
import pandas as pd

from utils import CLEAN_DIR, REPORTS_DIR, ROOT

TRUTH_DIR = ROOT / "data" / "truth"
DATES = {"vendors": ["onboarding_date"], "purchase_orders": ["order_date", "promised_date"],
         "deliveries": ["received_date"], "sales": ["month"], "inventory": ["snapshot_date"]}


def load(folder, name):
    df = pd.read_csv(folder / f"{name}.csv", dtype={"line_no": int})
    for c in DATES.get(name, []):
        df[c] = pd.to_datetime(df[c].astype(str).str[:10])
    return df


rows, imputed_rows, coverage = [], [], []


def compare(table, keys, fields, imputed=None, tolerance=None):
    """Exact-match accuracy per field, plus closeness for imputed values (judged with a tolerance)."""
    imputed, tolerance = imputed or {}, tolerance or {}
    truth, clean = load(TRUTH_DIR, table), load(CLEAN_DIR, table)
    m = clean.merge(truth, on=keys, suffixes=("", "_true"))
    coverage.append({"table": table, "truth_rows": len(truth), "clean_rows": len(clean), "matched": len(m)})
    flags = m.get("dq_flags", pd.Series("", index=m.index)).fillna("")
    for f in fields:
        a, b = m[f], m[f + "_true"]
        same = (a - b).abs() <= 0.011 if pd.api.types.is_float_dtype(a) else (a == b)
        same = same | (a.isna() & b.isna())
        imp = flags.str.contains(imputed[f]) if f in imputed else pd.Series(False, index=m.index)
        excluded = a.isna() & b.notna() if f == "qty_rejected" else pd.Series(False, index=m.index)
        base = ~imp & ~excluded
        rows.append({"table": table, "field": f, "compared": int(base.sum()), "matching": int(same[base].sum())})
        if imp.any():
            if pd.api.types.is_datetime64_any_dtype(a):
                err = (a - b).dt.days.abs()[imp]
                unit = "days"
            elif f in ("unit_price", "qty_sold"):  # relative error: magnitudes differ widely across items
                diff = (a - b).abs()
                err = (diff / b.where(b != 0) * 100).fillna((diff > 0) * 100.0)[imp]
                unit = "%"
            else:
                err = (a - b).abs()[imp]
                unit = "units"
            imputed_rows.append({"table": table, "field": f, "rule": imputed[f], "rows": int(imp.sum()),
                                 "exact": int(same[imp].sum()), "median_error": f"{err.median():.1f} {unit}",
                                 "within_tolerance": f"{(err <= tolerance[f]).mean():.1%} (≤ {tolerance[f]} {unit})"})


compare("vendors", ["vendor_id"], ["vendor_name", "category", "city", "state", "onboarding_date"])
compare("items", ["item_id"], ["item_name", "category", "unit_of_measure", "standard_price"])
compare("purchase_orders", ["po_id", "line_no"],
        ["order_date", "vendor_id", "item_id", "quantity", "unit_price", "order_type", "promised_date", "buyer_id"],
        imputed={"unit_price": "price_imputed", "promised_date": "promised_imputed", "quantity": "qty_from_receipts"},
        tolerance={"unit_price": 10, "promised_date": 3, "quantity": 0})
compare("deliveries", ["delivery_id"], ["po_id", "line_no", "received_date", "qty_received", "qty_rejected"],
        imputed={"qty_rejected": "rejected_blank_set_0"}, tolerance={"qty_rejected": 0})
compare("sales", ["item_id", "month"], ["qty_sold"], imputed={"qty_sold": "qty_imputed"},
        tolerance={"qty_sold": 25})
compare("inventory", ["item_id", "snapshot_date"], ["qty_on_hand"])

acc = pd.DataFrame(rows)
acc["accuracy"] = acc.matching / acc.compared
cov = pd.DataFrame(coverage)
cov["recall"] = cov.matched / cov.truth_rows
total_compared, total_matching = acc.compared.sum(), acc.matching.sum()
overall = total_matching / total_compared

lines = ["# Cleaning Validation — Cleaned Data vs Ground Truth", "",
         "`data/truth/` holds the data as it was before the data-quality problems were injected. "
         "It is not used by the cleaning; this report only measures the result.", "",
         f"**Overall: {total_matching:,} of {total_compared:,} cleaned values ({overall:.2%}) exactly match the "
         "true values** (imputed values are scored separately below).", "",
         "## Row coverage", "", cov.to_markdown(index=False, floatfmt=".2%"), "",
         "Rows in the truth but not in the clean data were removed on purpose: PO lines with no recoverable "
         "order date, and receipts whose PO number was corrupted (orphans), so they can't be linked to an order.", "",
         "## Field accuracy (values not imputed)", "",
         acc.to_markdown(index=False, floatfmt=".2%"), "",
         "## Imputed values (estimates, so judged by closeness)", "",
         pd.DataFrame(imputed_rows).to_markdown(index=False), ""]
(REPORTS_DIR / "cleaning_validation.md").write_text("\n".join(lines), encoding="utf-8")

print(cov.to_string(index=False))
print(acc.to_string(index=False))
print(pd.DataFrame(imputed_rows).to_string(index=False))
print(f"\nOverall exact accuracy: {overall:.4%} ({total_matching:,}/{total_compared:,})")
