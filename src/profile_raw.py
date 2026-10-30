"""
Run every data-quality check on the raw CSVs and write reports/raw_data_profile.md.

Each check records how many rows it affects, examples, and the handling rule that
Phase 3 (cleaning) will apply. Nothing in data/raw is modified.

Run from the project root:
    .venv/Scripts/python src/profile_raw.py
"""
import pandas as pd

from utils import (REPORTS_DIR, date_format_of, normalize_vendor_name, parse_mixed_date, parse_price,
                   read_raw, vendor_core_name)

issues = []


def add(table, check, flags, total, action, examples=None):
    n = int(flags.sum()) if hasattr(flags, "sum") else int(flags)
    ex = ""
    if examples is not None and n:
        ex = "; ".join(f"`{x}`" for x in pd.Series(examples).astype(str).drop_duplicates().head(3))
    issues.append({"table": table, "check": check, "rows": n, "pct": 100 * n / total if total else 0,
                   "example": ex.replace("|", "/"), "action": action})


def canonical_by_majority(s):
    """Map each value to the most common spelling among values equal after strip+lower."""
    key = s.str.strip().str.lower()
    best = s.groupby(key).agg(lambda x: x.value_counts().index[0])
    return key.map(best)


# --------------------------------------------------------------------------------------
# vendors
# --------------------------------------------------------------------------------------
vend = read_raw("vendors")
n = len(vend)
add("vendors", "Duplicate vendor_id", vend.vendor_id.duplicated(), n, "Delete (keep first)")

vend["norm"], vend["core"] = normalize_vendor_name(vend.vendor_name), vendor_core_name(vend.vendor_name)
pairs = vend.merge(vend, on=["core", "category", "city"], suffixes=("", "_other"))
pairs = pairs[pairs.vendor_id < pairs.vendor_id_other]
# Vendor codes are issued sequentially, so the lower code is the original registration.
# (onboarding_date is not reliable here: duplicates were sometimes given an earlier date.)
dup_map = dict(zip(pairs.vendor_id_other, pairs.vendor_id))
add("vendors", "Same supplier registered twice (same core name + category + city)", len(dup_map), n,
    "Map duplicate code -> original (lower, first-issued code) in a vendor_id_map table; drop duplicate record",
    [f"{d}->{o}" for d, o in dup_map.items()])

state_canon = canonical_by_majority(vend.state)
codes = vend.state.str.strip().str.fullmatch(r"[A-Za-z]{2}")
add("vendors", "State written as 2-letter code", codes, n, "Map code -> full state name (MH -> Maharashtra)",
    vend.state[codes])
add("vendors", "State with wrong case / trailing spaces", (vend.state != state_canon) & ~codes, n,
    "Trim + title case", vend.state[(vend.state != state_canon) & ~codes])
add("vendors", "Blank payment_terms", vend.payment_terms.str.strip() == "", n,
    "Keep vendor; set payment_terms = 'Unknown'")
fmt = date_format_of(vend.onboarding_date)
add("vendors", "onboarding_date not in ISO format", ~fmt.isin(["iso"]), n, "Parse DD/MM/YYYY -> DATE",
    vend.onboarding_date[fmt != "iso"])

# --------------------------------------------------------------------------------------
# items
# --------------------------------------------------------------------------------------
items = read_raw("items")
n = len(items)
add("items", "Duplicate item_id", items.item_id.duplicated(), n, "Delete (keep first)")
add("items", "standard_price stored as text with ₹ / commas", items.standard_price.str.startswith("₹"), n,
    "Strip ₹ and commas -> DECIMAL", items.standard_price[items.standard_price.str.startswith("₹")])
std_price = parse_price(items.standard_price)
add("items", "standard_price missing / unparseable / <= 0", std_price.isna() | (std_price <= 0), n,
    "Investigate (none expected)")
cat_canon = canonical_by_majority(items.category)
add("items", "category with wrong case / trailing spaces", items.category != cat_canon, n,
    "Trim + map to the 7 canonical categories", items.category[items.category != cat_canon])
add("items", "Blank unit_of_measure", items.unit_of_measure.str.strip() == "", n,
    "Fill from items with the same base name (e.g. other 'TMT Bar ...' items are in tonne)")

# --------------------------------------------------------------------------------------
# purchase_orders
# --------------------------------------------------------------------------------------
po_raw = read_raw("purchase_orders")
n = len(po_raw)
exact = po_raw.duplicated()
add("purchase_orders", "Exact duplicate rows", exact, n, "Delete (keep first)", po_raw.po_id[exact])
po = po_raw[~exact].copy()
add("purchase_orders", "Same (po_id, line_no) with conflicting values", po.duplicated(["po_id", "line_no"]), n,
    "Investigate (none expected)")

# Vendor id / name
vid = po.vendor_id.str.strip()
blank_vid = vid == ""
add("purchase_orders", "Blank vendor_id", blank_vid, n,
    "Recover from other lines of the same PO, else from vendor_name match", po.po_id[blank_vid])
add("purchase_orders", "vendor_id not in vendor master", ~blank_vid & ~vid.isin(vend.vendor_id), n,
    "Investigate (none expected)")
add("purchase_orders", "vendor_id is a duplicate vendor registration", vid.isin(dup_map), n,
    "Remap to original vendor_id via vendor_id_map", vid[vid.isin(dup_map)])

po_vid_from_po = po.assign(v=vid.replace("", pd.NA)).groupby("po_id")["v"].agg(lambda x: x.dropna().unique())
recover_same_po = blank_vid & po.po_id.map(po_vid_from_po.map(len)).eq(1)
core_to_ids = vend.assign(v=vend.vendor_id.replace(dup_map)).groupby("core")["v"].agg(lambda x: set(x))
name_ids = vendor_core_name(po.vendor_name).map(core_to_ids)
recover_by_name = blank_vid & ~recover_same_po & name_ids.map(lambda s: isinstance(s, set) and len(s) == 1)
add("purchase_orders", "  ...of which recoverable from another line of the same PO", recover_same_po, n,
    "Fill vendor_id from the PO's other lines")
add("purchase_orders", "  ...of which recoverable only by vendor_name match", recover_by_name, n,
    "Fill vendor_id from the unique vendor with that name")
add("purchase_orders", "  ...of which NOT recoverable", blank_vid & ~recover_same_po & ~recover_by_name, n,
    "Keep line with vendor_id = NULL, flag 'vendor_unknown'")

master = vend.set_index("vendor_id")
differs = ~blank_vid & (po.vendor_name != vid.map(master["vendor_name"]))
same_vendor = vendor_core_name(po.vendor_name) == vid.map(master["core"])
add("purchase_orders", "vendor_name differs from master (case/spacing/suffix only)", differs & same_vendor, n,
    "Ignore PO vendor_name; use vendor master name via vendor_id", po.vendor_name[differs & same_vendor])
add("purchase_orders", "vendor_name points to a different vendor than vendor_id", differs & ~same_vendor, n,
    "Investigate (none expected)")

add("purchase_orders", "item_id not in item master", ~po.item_id.isin(items.item_id), n,
    "Investigate (none expected)")

# Dates
for col in ["order_date", "promised_date"]:
    f = date_format_of(po[col])
    add("purchase_orders", f"{col} in DD/MM/YYYY format", f == "dd/mm/yyyy", n, "Parse as day-first -> DATE",
        po[col][f == "dd/mm/yyyy"])
    add("purchase_orders", f"{col} in D-Mon-YY format", f == "d-mon-yy", n, "Parse -> DATE",
        po[col][f == "d-mon-yy"])
    add("purchase_orders", f"{col} in an unknown format", f == "unknown", n, "Investigate (none expected)",
        po[col][f == "unknown"])

dmy = po.order_date[date_format_of(po.order_date) == "dd/mm/yyyy"].str.split("/", expand=True).astype(int)
dd_mm_evidence = (int((dmy[0] > 12).sum()), int((dmy[1] > 12).sum()))

po["od"], po["pd"] = parse_mixed_date(po.order_date), parse_mixed_date(po.promised_date)
od_by_po = po.groupby("po_id")["od"].agg(lambda x: x.dropna().unique())
blank_od = po.od.isna()
add("purchase_orders", "Blank order_date", blank_od, n, "Fill from the other lines of the same PO",
    po.po_id[blank_od])
add("purchase_orders", "  ...of which NOT recoverable from the same PO", blank_od & po.po_id.map(od_by_po.map(len)).ne(1), n,
    "Drop line (no date = cannot be used in any time-based KPI)")
add("purchase_orders", "PO lines with more than one order_date in the same PO", po.po_id.map(od_by_po.map(len)).gt(1), n,
    "Investigate (none expected)")
add("purchase_orders", "Blank promised_date", po.pd.isna(), n,
    "Impute = order_date + median promised lead time of that vendor & order type; flag 'promised_imputed'",
    po.po_id[po.pd.isna()])
add("purchase_orders", "promised_date before order_date", po.pd < po.od, n, "Investigate (none expected)")

# Prices and quantities
price = parse_price(po.unit_price)
add("purchase_orders", "unit_price stored as text with ₹ / commas", po.unit_price.str.startswith("₹"), n,
    "Strip ₹ and commas -> DECIMAL", po.unit_price[po.unit_price.str.startswith("₹")])
add("purchase_orders", "Blank unit_price", price.isna(), n,
    "Impute = median price for same item + vendor in the same quarter; flag 'price_imputed'")
ratio = price / price.groupby(po.item_id).transform("median")
add("purchase_orders", "unit_price ~100x the item's median (entered in paise)", ratio.between(50, 200), n,
    "Divide by 100; flag 'price_fixed_x100'", po.unit_price[ratio.between(50, 200)])
add("purchase_orders", "Other unit_price outliers (>5x or <0.2x item median)",
    (ratio > 5) & ~ratio.between(50, 200) | (ratio < 0.2), n, "Review; keep (bulk/urgent prices fall well inside this band)")
qty = pd.to_numeric(po.quantity, errors="coerce")
dl_qty = (read_raw("deliveries").drop_duplicates().assign(r=lambda d: pd.to_numeric(d.qty_received))
          .groupby(["po_id", "line_no"])["r"].sum())
has_receipt = pd.Series(po.set_index(["po_id", "line_no"]).index.isin(dl_qty.index), index=po.index)
add("purchase_orders", "quantity zero", qty == 0, n, "See the two rows below")
add("purchase_orders", "  ...of which goods were received", (qty == 0) & has_receipt, n,
    "Set quantity = total received; flag 'qty_from_receipts' (0 was a typo, goods arrived)")
add("purchase_orders", "  ...of which nothing was received", (qty == 0) & ~has_receipt, n,
    "Drop line (no evidence of a real order)")
add("purchase_orders", "quantity negative", qty < 0, n,
    "Take absolute value; flag 'qty_sign_fixed' (sign typo — receipts confirm the positive quantity)",
    po.quantity[qty < 0])
add("purchase_orders", "quantity not a whole number / unparseable", qty.isna() | (qty % 1 != 0), n,
    "Investigate (none expected)")

ot = po.order_type.str.strip().str.title()
add("purchase_orders", "order_type with wrong case / trailing spaces", po.order_type != ot, n,
    "Trim + title case -> Regular / Bulk / Urgent", po.order_type[po.order_type != ot])
add("purchase_orders", "order_type not Regular/Bulk/Urgent after trimming", ~ot.isin(["Regular", "Bulk", "Urgent"]), n,
    "Investigate (none expected)")
add("purchase_orders", "buyer_id not in format Bnn", ~po.buyer_id.str.fullmatch(r"B\d{2}"), n,
    "Investigate (none expected)")

# --------------------------------------------------------------------------------------
# deliveries
# --------------------------------------------------------------------------------------
dl_raw = read_raw("deliveries")
n = len(dl_raw)
exact = dl_raw.duplicated()
add("deliveries", "Exact duplicate rows", exact, n, "Delete (keep first)", dl_raw.delivery_id[exact])
dl = dl_raw[~exact].copy()
add("deliveries", "Duplicate delivery_id with conflicting values", dl.delivery_id.duplicated(), n,
    "Investigate (none expected)")

po_keys = po[["po_id", "line_no", "od", "quantity"]].assign(quantity=qty.abs())
dl = dl.merge(po_keys, on=["po_id", "line_no"], how="left", indicator=True)
orphan = dl._merge == "left_only"
add("deliveries", "Receipt for a PO line that does not exist (orphan)", orphan, n,
    "Move to a rejected-rows table; exclude from KPIs", dl.po_id[orphan])

f = date_format_of(dl.received_date)
add("deliveries", "received_date in DD/MM/YYYY or D-Mon-YY format", f.isin(["dd/mm/yyyy", "d-mon-yy"]), n,
    "Parse -> DATE", dl.received_date[f != "iso"])
add("deliveries", "received_date blank / unknown format", f.isin(["blank", "unknown"]), n,
    "Investigate (none expected)")
dl["rd"] = parse_mixed_date(dl.received_date)
early = dl.rd < dl.od
gap = (dl.od - dl.rd).dt.days
add("deliveries", "received_date before order_date", early, n,
    "Wrong year typed: add 1 year; flag 'year_fixed'. Drop if still before order_date after the fix",
    dl.received_date[early])
add("deliveries", "  ...of which still before order_date after adding 1 year",
    early & (dl.rd + pd.DateOffset(years=1) < dl.od), n, "Drop receipt")
add("deliveries", "  ...of which the gap is NOT 330-400 days (i.e. long-delayed receipts)",
    early & ~gap.between(330, 400), n, "Same rule (+1 year): these were delivered months late",
    (dl.received_date + " vs order " + dl.od.dt.strftime("%Y-%m-%d"))[early & ~gap.between(330, 400)])

rcv = pd.to_numeric(dl.qty_received, errors="coerce")
rej = pd.to_numeric(dl.qty_rejected, errors="coerce")
add("deliveries", "qty_received zero / negative / unparseable", ~(rcv > 0), n, "Investigate (none expected)")
add("deliveries", "Blank qty_rejected", dl.qty_rejected.str.strip() == "", n,
    "Set to 0 (blank = no rejection recorded at inspection)")
add("deliveries", "qty_rejected greater than qty_received", rej > rcv, n,
    "Set to NULL; flag 'rejected_invalid'; exclude from rejection-rate KPI",
    (dl.qty_rejected + " > " + dl.qty_received)[rej > rcv])
tot = dl[~orphan].assign(r=rcv).groupby(["po_id", "line_no"]).agg(r=("r", "sum"), q=("quantity", "first"))
add("deliveries", "PO lines where total received > ordered (excl. lines ordered as 0)",
    ((tot.r > tot.q) & (tot.q > 0)).sum(), len(tot), "Investigate (none expected)")
open_lines = ~po.set_index(["po_id", "line_no"]).index.isin(tot.index)
add("purchase_orders", "PO lines with no receipt yet (open)", open_lines, len(po),
    "Keep; status = 'Open'. Exclude from delivery KPIs, include in spend",
    po.order_date[open_lines].tail(3))

# --------------------------------------------------------------------------------------
# sales / inventory
# --------------------------------------------------------------------------------------
sales = read_raw("sales")
n = len(sales)
add("sales", "Exact duplicate rows", sales.duplicated(), n, "Delete (keep first)")
mon = sales.month.str.fullmatch(r"[A-Za-z]{3}-\d{4}")
add("sales", "month written as Mon-YYYY", mon, n, "Convert to first day of month (DATE)", sales.month[mon])
add("sales", "month in an unknown format", ~mon & ~sales.month.str.fullmatch(r"\d{4}-\d{2}"), n,
    "Investigate (none expected)")
sales["m"] = pd.to_datetime(sales.month.where(~mon, pd.to_datetime(sales.month[mon], format="%b-%Y").dt.strftime("%Y-%m")),
                            format="%Y-%m")
s1 = sales.drop_duplicates()
add("sales", "Same (item, month) twice after fixing format, with different qty", s1.duplicated(["item_id", "m"]), n,
    "Investigate (none expected)")
add("sales", "Blank qty_sold", sales.qty_sold.str.strip() == "", n,
    "Impute = average of the item's previous and next month; flag 'qty_imputed'")
add("sales", "item_id not in item master", ~sales.item_id.isin(items.item_id), n, "Investigate (none expected)")
cover = s1.groupby("item_id")["m"].nunique()
add("sales", "Items without all 36 months", (cover != 36).sum(), len(cover), "Investigate (none expected)")

inv = read_raw("inventory")
n = len(inv)
q_inv = pd.to_numeric(inv.qty_on_hand, errors="coerce")
add("inventory", "Negative qty_on_hand", q_inv < 0, n,
    "Take absolute value; flag (stock cannot be negative; sign typo)", inv.qty_on_hand[q_inv < 0])
add("inventory", "Duplicate (item_id, snapshot_date)", inv.duplicated(["item_id", "snapshot_date"]), n,
    "Investigate (none expected)")
add("inventory", "item_id not in item master", ~inv.item_id.isin(items.item_id), n, "Investigate (none expected)")
add("inventory", "Items missing a snapshot", (inv.groupby("item_id").size() != 2).sum(), inv.item_id.nunique(),
    "Investigate (none expected)")

# --------------------------------------------------------------------------------------
# Sanity checks: does the data look like real procurement data?
# --------------------------------------------------------------------------------------
po["price"], po["qty"] = price, qty.abs()
po["price"] = po.price.where(~ratio.between(50, 200), po.price / 100)
po = po.merge(items.assign(category=cat_canon)[["item_id", "category"]], on="item_id")
po["value"] = po.price * po.qty
po["year"] = po.od.dt.year
first_rcpt = dl[~orphan].groupby(["po_id", "line_no"])["rd"].min().rename("first_rd").reset_index()
lt = po.merge(first_rcpt, on=["po_id", "line_no"])
lt["lead"] = (lt.first_rd - lt.od).dt.days
lt["on_time"] = lt.first_rd <= lt.pd

by_year = po.groupby("year").agg(lines=("po_id", "size"), spend_cr=("value", lambda x: x.sum() / 1e7))
by_month = po.groupby(po.od.dt.month)["po_id"].size()
by_cat = lt.groupby("category").agg(median_lead_days=("lead", "median"), on_time_pct=("on_time", "mean"),
                                    median_line_value=("value", "median"))
by_cat["on_time_pct"] *= 100
by_type = ot.value_counts()

# --------------------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------------------
df = pd.DataFrame(issues)
lines = ["# Raw Data Profile — Data-Quality Checks", "",
         "Generated by `src/profile_raw.py` from `data/raw/`. Every check lists the rows affected and the "
         "handling rule Phase 3 will apply. Rows marked *Investigate (none expected)* are integrity checks "
         "that passed if the count is 0.", "",
         "## Summary", ""]
found = df[(df.rows > 0) & ~df.check.str.startswith("  ")]
passed = df[(df.rows == 0)]
lines += [f"- **{len(df)} checks run** on 6 tables · **{len(found)} issue types found** · "
          f"**{len(passed)} checks passed with 0 rows**",
          f"- Date convention: of the `dd/mm/yyyy`-style order dates, **{dd_mm_evidence[0]:,}** have a first part "
          f"> 12 and **{dd_mm_evidence[1]:,}** have a second part > 12, so the format is DD/MM/YYYY (not MM/DD).",
          f"- Duplicate vendor registrations found: "
          + ", ".join(f"{d} → {o} ({vend.set_index('vendor_id').at[d, 'vendor_name'].strip()!r} = "
                      f"{vend.set_index('vendor_id').at[o, 'vendor_name']!r})" for d, o in dup_map.items()),
          ""]

for table in ["vendors", "items", "purchase_orders", "deliveries", "sales", "inventory"]:
    t = df[df.table == table]
    lines += [f"## {table}", "", "| Check | Rows | % | Examples | Handling rule (Phase 3) |",
              "|---|---:|---:|---|---|"]
    for r in t.itertuples():
        status = "✅ " if r.rows == 0 else ""
        lines.append(f"| {status}{r.check.replace('  ...', '↳ ')} | {r.rows:,} | {r.pct:.2f} | {r.example} | "
                     f"{'—' if r.rows == 0 else r.action} |")
    lines.append("")

lines += ["## Sanity checks (does it look like real procurement data?)", "",
          "Computed on de-duplicated rows with dates/prices parsed (not yet fully cleaned).", "",
          "**Volume and spend by year** (should grow ~10%/year):", "",
          by_year.round(1).to_markdown(), "",
          "**PO lines by order month** (expect March financial-year-end and Oct–Dec peaks):", "",
          by_month.rename("lines").to_frame().T.to_markdown(index=False), "",
          "**By category:**", "",
          by_cat.round(1).to_markdown(), "",
          "**Order types:**", "",
          by_type.rename("lines").to_frame().T.to_markdown(index=False), ""]

out = REPORTS_DIR / "raw_data_profile.md"
out.write_text("\n".join(lines), encoding="utf-8")
print(df.to_string())
print("\nYear:\n", by_year.round(1), "\nMonth:\n", by_month.to_dict(), "\nCategory:\n", by_cat.round(1),
      "\nTypes:", by_type.to_dict())
print(f"\nDD/MM evidence: first>12={dd_mm_evidence[0]}, second>12={dd_mm_evidence[1]}")
print(f"Wrote {out}")
