"""
Phase 3, step 2: apply the context-aware cleaning rules and load the clean tables.

Reads the std_* views (types and spellings already standardised in sql/03_standardize.sql),
applies the handling rules from reports/raw_data_profile.md, then:
  - writes the clean tables in procurement_db (their PK/FK/CHECK constraints are the final gate)
  - records every removed row in rejected_rows with its reason
  - exports data/clean/*.csv
  - writes reports/cleaning_log.md

Run from the project root (after sql/03_standardize.sql):
    .venv/Scripts/python src/clean_data.py
"""
from collections import Counter

import numpy as np
import pandas as pd
from sqlalchemy import text

from db import get_engine
from utils import CLEAN_DIR, REPORTS_DIR, normalize_vendor_name, vendor_core_name

engine = get_engine()
log = []        # (table, kind, description, rows)
rejected = []   # rows for the rejected_rows table


def read(view, dates=()):
    df = pd.read_sql(f"SELECT * FROM {view}", engine)
    for col in dates:
        df[col] = pd.to_datetime(df[col])
    return df


def note(table, kind, description, rows):
    log.append((table, kind, description, int(rows)))


def flag(df, mask, name):
    """Append a data-quality flag to dq_flags for the masked rows."""
    mask = mask.fillna(False) if hasattr(mask, "fillna") else mask
    current = df.loc[mask, "dq_flags"]
    df.loc[mask, "dq_flags"] = np.where(current == "", name, current + "," + name)
    note(df.attrs["table"], "fixed", name, mask.sum())


def reject(df, mask, reason):
    mask = mask.fillna(False) if hasattr(mask, "fillna") else mask
    table = df.attrs["table"]
    rejected.extend({"source_table": table, "src_row": int(r), "reason": reason} for r in df.loc[mask, "src_row"])
    note(table, "removed", reason, mask.sum())
    out = df[~mask].copy()
    out.attrs["table"] = table
    return out


def start(df, table):
    df.attrs["table"] = table
    df["dq_flags"] = ""
    note(table, "in", "rows read from staging", len(df))
    return df


def drop_exact_duplicates(df):
    cols = [c for c in df.columns if c not in ("src_row", "dq_flags")]
    return reject(df, df.duplicated(cols), "exact duplicate row")


def median_fill(df, target, group_levels):
    """Fill NaNs in `target` with the group median, trying each grouping level in turn."""
    filled = df[target].copy()
    for keys in group_levels:
        med = df.groupby(keys)[target].transform("median")
        filled = filled.fillna(med)
    return filled


# --------------------------------------------------------------------------------------
# vendors
# --------------------------------------------------------------------------------------
v = start(read("std_vendors", ["onboarding_date"]), "vendors")
v["core"] = vendor_core_name(v.vendor_name)
pairs = v.merge(v, on=["core", "category", "city"], suffixes=("", "_dup"))
pairs = pairs[pairs.vendor_id < pairs.vendor_id_dup]   # lower (first-issued) code is the original
dup_map = dict(zip(pairs.vendor_id_dup, pairs.vendor_id))
for dup, orig in dup_map.items():
    v = reject(v, v.vendor_id == dup, f"duplicate registration of {orig}")
no_terms = v.payment_terms.isna()
v["payment_terms"] = v.payment_terms.fillna("Unknown")
note("vendors", "fixed", "payment_terms_unknown", no_terms.sum())
vendors = v[["vendor_id", "vendor_name", "category", "city", "state", "onboarding_date", "payment_terms"]]
vendor_id_map = pd.DataFrame({"raw_vendor_id": list(dup_map), "vendor_id": list(dup_map.values())})

# --------------------------------------------------------------------------------------
# items
# --------------------------------------------------------------------------------------
it = start(read("std_items"), "items")
words = it.item_name.str.split()


def uom_from_similar(i):
    """Unit of measure of the items sharing the longest name prefix in the same category."""
    same_cat = it[(it.category == it.at[i, "category"]) & it.unit_of_measure.notna()]
    for n in range(len(words[i]) - 1, 0, -1):
        prefix = " ".join(words[i][:n]) + " "
        match = same_cat[same_cat.item_name.str.startswith(prefix)]
        if len(match):
            return match.unit_of_measure.mode()[0]
    return None


no_uom = it.unit_of_measure.isna()
it.loc[no_uom, "unit_of_measure"] = [uom_from_similar(i) for i in it.index[no_uom]]
note("items", "fixed", "uom_from_similar_items", no_uom.sum())
it["standard_price"] = it.standard_price.astype(float)
items = it[["item_id", "item_name", "category", "unit_of_measure", "standard_price"]]

# --------------------------------------------------------------------------------------
# purchase_orders
# --------------------------------------------------------------------------------------
po = start(read("std_purchase_orders", ["order_date", "promised_date"]), "purchase_orders")
po["unit_price"] = po.unit_price.astype(float)
raw_po_keys = set(zip(po.po_id, po.line_no))
po = drop_exact_duplicates(po)

# Vendor: duplicate codes -> original; blanks from the same PO, else from the vendor name
dup_code = po.vendor_id.isin(dup_map)
po.loc[dup_code, "vendor_id"] = po.loc[dup_code, "vendor_id"].map(dup_map)
flag(po, dup_code, "vendor_remapped")

vid_by_po = po.dropna(subset=["vendor_id"]).groupby("po_id")["vendor_id"].agg(lambda x: set(x))
from_po = po.vendor_id.isna() & po.po_id.map(vid_by_po).map(lambda s: isinstance(s, set) and len(s) == 1)
po.loc[from_po, "vendor_id"] = po.loc[from_po, "po_id"].map(vid_by_po).map(lambda s: next(iter(s)))
flag(po, from_po, "vendor_from_po")

v_all = read("std_vendors").assign(final=lambda d: d.vendor_id.replace(dup_map))
for name_key, label in [(normalize_vendor_name, "vendor_from_name"), (vendor_core_name, "vendor_from_core_name")]:
    lookup = v_all.assign(k=name_key(v_all.vendor_name)).groupby("k")["final"].agg(lambda x: set(x))
    cands = name_key(po.vendor_name).map(lookup)
    ok = po.vendor_id.isna() & cands.map(lambda s: isinstance(s, set) and len(s) == 1)
    po.loc[ok, "vendor_id"] = cands[ok].map(lambda s: next(iter(s)))
    flag(po, ok, label)
flag(po, po.vendor_id.isna(), "vendor_unknown")

# Order date: from the other lines of the same PO, else the line cannot be used
od_by_po = po.dropna(subset=["order_date"]).groupby("po_id")["order_date"].agg(lambda x: set(x))
fill_od = po.order_date.isna() & po.po_id.map(od_by_po).map(lambda s: isinstance(s, set) and len(s) == 1)
po.loc[fill_od, "order_date"] = po.loc[fill_od, "po_id"].map(od_by_po).map(lambda s: next(iter(s)))
flag(po, fill_od, "order_date_from_po")
po = reject(po, po.order_date.isna(), "order_date missing and not recoverable from the same PO")

# Quantity: negative = sign typo; zero = typo if goods were received, else not a real order
received = (read("std_deliveries").drop_duplicates(subset=["delivery_id"])
            .groupby(["po_id", "line_no"])["qty_received"].sum())
neg = po.quantity < 0
po.loc[neg, "quantity"] = -po.loc[neg, "quantity"]
flag(po, neg, "qty_sign_fixed")
rcv = pd.Series([received.get(k, 0) for k in zip(po.po_id, po.line_no)], index=po.index)
from_rcv = (po.quantity == 0) & (rcv > 0)
po.loc[from_rcv, "quantity"] = rcv[from_rcv]
flag(po, from_rcv, "qty_from_receipts")
po = reject(po, po.quantity == 0, "quantity 0 and nothing received")

# Price: paise-entry errors (~100x the item median), then impute blanks from similar orders
ratio = po.unit_price / po.groupby("item_id")["unit_price"].transform("median")
x100 = ratio.between(50, 200)
po.loc[x100, "unit_price"] = (po.loc[x100, "unit_price"] / 100).round(2)
flag(po, x100, "price_fixed_x100")
po["year"] = po.order_date.dt.year
no_price = po.unit_price.isna()
po["unit_price"] = median_fill(po, "unit_price", [["item_id", "vendor_id", "order_type", "year"],
                                                  ["item_id", "order_type", "year"],
                                                  ["item_id", "order_type"], ["item_id"]]).round(2)
flag(po, no_price, "price_imputed")

# Promised date: order date + the vendor's usual promised lead time for that order type
po["lead"] = (po.promised_date - po.order_date).dt.days
no_promise = po.promised_date.isna()
lead = median_fill(po, "lead", [["vendor_id", "order_type"], ["order_type"]]).round()
po.loc[no_promise, "promised_date"] = po.loc[no_promise, "order_date"] + pd.to_timedelta(lead[no_promise], unit="D")
flag(po, no_promise, "promised_imputed")

assert not po.duplicated(["po_id", "line_no"]).any(), "duplicate PO line keys after cleaning"
purchase_orders = po[["po_id", "line_no", "order_date", "vendor_id", "item_id", "quantity", "unit_price",
                      "order_type", "promised_date", "buyer_id", "dq_flags"]]

# --------------------------------------------------------------------------------------
# deliveries
# --------------------------------------------------------------------------------------
dl = start(read("std_deliveries", ["received_date"]), "deliveries")
dl = drop_exact_duplicates(dl)
assert not dl.delivery_id.duplicated().any(), "conflicting delivery_id duplicates"

keys = pd.Series(list(zip(dl.po_id, dl.line_no)), index=dl.index)
dl = reject(dl, ~keys.isin(raw_po_keys), "orphan: PO line does not exist")
keys = pd.Series(list(zip(dl.po_id, dl.line_no)), index=dl.index)
kept_keys = set(zip(purchase_orders.po_id, purchase_orders.line_no))
dl = reject(dl, ~keys.isin(kept_keys), "parent PO line removed during cleaning")

dl = dl.merge(purchase_orders[["po_id", "line_no", "order_date"]], on=["po_id", "line_no"], how="left")
dl.attrs["table"] = "deliveries"
early = dl.received_date < dl.order_date
dl.loc[early, "received_date"] = dl.loc[early, "received_date"] + pd.DateOffset(years=1)
flag(dl, early, "year_fixed")
dl = reject(dl, dl.received_date < dl.order_date, "received before order even after year fix")

invalid_rej = dl.qty_rejected > dl.qty_received
blank_rej = dl.qty_rejected.isna()
dl["qty_rejected"] = dl.qty_rejected.astype("Int64")
dl.loc[invalid_rej, "qty_rejected"] = pd.NA
flag(dl, invalid_rej, "rejected_invalid")
dl.loc[blank_rej, "qty_rejected"] = 0
flag(dl, blank_rej, "rejected_blank_set_0")
deliveries = dl[["delivery_id", "po_id", "line_no", "received_date", "qty_received", "qty_rejected", "dq_flags"]]

# --------------------------------------------------------------------------------------
# sales / inventory
# --------------------------------------------------------------------------------------
s = start(read("std_sales", ["month"]), "sales")
s = drop_exact_duplicates(s)
assert not s.duplicated(["item_id", "month"]).any(), "conflicting (item, month) sales rows"
s = s.sort_values(["item_id", "month"])
no_qty = s.qty_sold.isna()
neighbours = pd.concat([s.groupby("item_id")["qty_sold"].shift(1), s.groupby("item_id")["qty_sold"].shift(-1)], axis=1)
s.loc[no_qty, "qty_sold"] = neighbours[no_qty].mean(axis=1).round()
flag(s, no_qty, "qty_imputed")
s["qty_sold"] = s.qty_sold.astype(int)
sales = s[["item_id", "month", "qty_sold", "dq_flags"]]

inv = start(read("std_inventory", ["snapshot_date"]), "inventory")
neg = inv.qty_on_hand < 0
inv.loc[neg, "qty_on_hand"] = -inv.loc[neg, "qty_on_hand"]
flag(inv, neg, "qty_sign_fixed")
inventory = inv[["item_id", "snapshot_date", "qty_on_hand", "dq_flags"]]

# --------------------------------------------------------------------------------------
# Load clean tables (constraints in sql/01_schema.sql reject anything still invalid)
# --------------------------------------------------------------------------------------
clean = {"vendors": vendors, "vendor_id_map": vendor_id_map, "items": items,
         "purchase_orders": purchase_orders, "deliveries": deliveries, "sales": sales,
         "inventory": inventory, "rejected_rows": pd.DataFrame(rejected)}
with engine.begin() as conn:
    for table in reversed(clean):
        conn.execute(text(f"DELETE FROM {table}"))
CLEAN_DIR.mkdir(parents=True, exist_ok=True)
for table, df in clean.items():
    df = df.copy()
    if "dq_flags" in df:
        df["dq_flags"] = df.dq_flags.replace("", None)
    df.to_sql(table, engine, if_exists="append", index=False, chunksize=5000)
    df.to_csv(CLEAN_DIR / f"{table}.csv", index=False, date_format="%Y-%m-%d")
    note(table, "out", "rows written to clean table", len(df))

# --------------------------------------------------------------------------------------
# Cleaning log
# --------------------------------------------------------------------------------------
lg = pd.DataFrame(log, columns=["table", "kind", "description", "rows"])
lines = ["# Cleaning Log", "",
         "Produced by `sql/03_standardize.sql` (types, formats, spellings) and `src/clean_data.py` "
         "(duplicates, recovery, imputation, outliers). Removed rows are kept in the `rejected_rows` "
         "table with their reason; fixed rows carry their fixes in the `dq_flags` column.", "",
         "## Summary", "", "| Table | Rows in | Removed | Rows fixed (flags) | Rows out |", "|---|---:|---:|---:|---:|"]
for table in ["vendors", "items", "purchase_orders", "deliveries", "sales", "inventory"]:
    t = lg[lg.table == table]
    rows_in = t[t.kind == "in"].rows.sum()
    removed = t[t.kind == "removed"].rows.sum()
    fixed = t[t.kind == "fixed"].rows.sum()
    rows_out = t[t.kind == "out"].rows.sum()
    lines.append(f"| {table} | {rows_in:,} | {removed:,} | {fixed:,} | {rows_out:,} |")
lines.append("")
for table in ["vendors", "items", "purchase_orders", "deliveries", "sales", "inventory"]:
    t = lg[(lg.table == table) & lg.kind.isin(["removed", "fixed"]) & (lg.rows > 0)]
    if t.empty:
        continue
    lines += [f"## {table}", "", "| Action | Rule | Rows |", "|---|---|---:|"]
    lines += [f"| {r.kind} | {r.description} | {r.rows:,} |" for r in t.itertuples()]
    lines.append("")
lines += ["## Removed rows by reason", "", "| Source table | Reason | Rows |", "|---|---|---:|"]
for (tbl, reason), n in Counter((r["source_table"], r["reason"]) for r in rejected).most_common():
    lines.append(f"| {tbl} | {reason} | {n:,} |")
(REPORTS_DIR / "cleaning_log.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

print(lg[lg.kind != "in"].to_string(index=False))
print(f"\nRejected rows: {len(rejected):,}. Wrote {REPORTS_DIR / 'cleaning_log.md'}")
