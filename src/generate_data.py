"""
Generate a synthetic procurement dataset for the
"Procurement Efficiency through Vendor KPI Development & Risk Analytics" project.

Every table is written twice:
  data/truth/  clean ground-truth tables (used in Phase 3 to measure cleaning accuracy)
  data/raw/    the same data with realistic data-quality problems injected (the project input)

The data is synthetic but built to behave like a mid-sized Indian manufacturer's
procurement records for Jan 2023 - Dec 2025: vendor spend follows a Pareto curve,
some vendors are chronically late or ship poor quality, bulk orders get discounts,
monsoon months delay deliveries from some states, and some items are over-ordered.

Run from the project root:
    .venv/Scripts/python src/generate_data.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
START, END = pd.Timestamp("2023-01-01"), pd.Timestamp("2025-12-31")
N_PO_LINES = 50_000

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
TRUTH_DIR = ROOT / "data" / "truth"

rng = np.random.default_rng(SEED)

# --------------------------------------------------------------------------------------
# Reference data
# --------------------------------------------------------------------------------------
# po_share: share of purchase orders going to the category
# lead_days: typical promised lead time; line_value: typical order-line value (INR)
CATEGORIES = {
    "Raw Materials": {
        "n_vendors": 30, "n_items": 140, "po_share": 0.22, "lead_days": 14, "line_value": 400_000,
        "vendor_words": ["Steel", "Metals", "Ispat", "Alloys", "Iron & Steel"],
        "bases": [("TMT Bar", "tonne", 58000), ("MS Plate", "tonne", 62000), ("MS Angle", "tonne", 60000),
                  ("MS Channel", "tonne", 61000), ("Stainless Steel Sheet", "kg", 240),
                  ("Aluminium Sheet", "kg", 280), ("Copper Rod", "kg", 820), ("GI Pipe", "metre", 450),
                  ("Steel Billet", "tonne", 45000), ("Wire Rod", "tonne", 52000),
                  ("HR Coil", "tonne", 55000), ("CR Coil", "tonne", 63000)],
        "specs": ["6mm", "8mm", "10mm", "12mm", "16mm", "20mm", "25mm", "32mm", "40mm", "50mm", "Std", "HD"],
    },
    "Packaging": {
        "n_vendors": 22, "n_items": 120, "po_share": 0.15, "lead_days": 10, "line_value": 60_000,
        "vendor_words": ["Packaging", "Packers", "Polypack", "Cartons", "Pack Solutions"],
        "bases": [("Corrugated Box", "piece", 45), ("Stretch Film", "roll", 650), ("BOPP Tape", "roll", 55),
                  ("Bubble Wrap", "roll", 900), ("Wooden Pallet", "piece", 950), ("Plastic Crate", "piece", 380),
                  ("Shrink Wrap", "roll", 1200), ("Poly Bag", "piece", 4), ("Strapping Roll", "roll", 1500),
                  ("Paper Bag", "piece", 8), ("Foam Sheet", "piece", 120), ("Label Roll", "roll", 350)],
        "specs": ["Small", "Medium", "Large", "XL", "Type A", "Type B", "Type C", "Type D", "Printed", "Plain"],
    },
    "Electrical & Electronics": {
        "n_vendors": 25, "n_items": 140, "po_share": 0.17, "lead_days": 12, "line_value": 120_000,
        "vendor_words": ["Electricals", "Electronics", "Power Systems", "Switchgear", "Controls"],
        "bases": [("LED Panel", "piece", 1800), ("Copper Cable", "metre", 220), ("MCB", "piece", 450),
                  ("Contactor", "piece", 2600), ("Relay", "piece", 900), ("Switchgear Panel", "piece", 85000),
                  ("Transformer", "piece", 150000), ("Motor Starter", "piece", 7500),
                  ("PLC Module", "piece", 32000), ("Sensor", "piece", 4200), ("Cable Tray", "metre", 650),
                  ("Junction Box", "piece", 750)],
        "specs": ["6A", "10A", "16A", "32A", "63A", "1HP", "5HP", "10HP", "Single Phase", "Three Phase",
                  "IP65", "24V DC"],
    },
    "MRO": {
        "n_vendors": 28, "n_items": 160, "po_share": 0.22, "lead_days": 7, "line_value": 40_000,
        "vendor_words": ["Industrial Supplies", "Engineering", "Tools", "Hardware", "Industrial Services"],
        "bases": [("Bearing", "piece", 850), ("V-Belt", "piece", 650), ("Hydraulic Oil", "litre", 210),
                  ("Grease", "kg", 320), ("Safety Gloves", "pair", 120), ("Safety Helmet", "piece", 350),
                  ("Welding Rod", "kg", 260), ("Grinding Wheel", "piece", 180), ("Fastener Set", "box", 900),
                  ("Gasket", "piece", 150), ("Valve", "piece", 2800), ("Pump Seal", "piece", 3500),
                  ("Lubricant", "litre", 280), ("Cutting Disc", "piece", 60)],
        "specs": ["Size S", "Size M", "Size L", "Size XL", "Grade 1", "Grade 2", "Industrial", "Heavy Duty",
                  "Std Pack", "Bulk Pack", "Type A", "Type B"],
    },
    "IT Hardware": {
        "n_vendors": 15, "n_items": 70, "po_share": 0.06, "lead_days": 18, "line_value": 300_000,
        "vendor_words": ["Infotech", "Technologies", "Systems", "IT Solutions", "Computers"],
        "bases": [("Laptop", "piece", 65000), ("Desktop", "piece", 48000), ("Monitor", "piece", 14000),
                  ("Printer", "piece", 22000), ("Network Switch", "piece", 28000), ("Router", "piece", 9000),
                  ("UPS", "piece", 18000), ("Server Rack", "piece", 120000), ("SSD", "piece", 7000),
                  ("RAM Module", "piece", 4500)],
        "specs": ["Basic", "Standard", "Pro", "Enterprise", "Gen 4", "Gen 5", "Lite", "Max"],
    },
    "Chemicals": {
        "n_vendors": 15, "n_items": 90, "po_share": 0.10, "lead_days": 12, "line_value": 80_000,
        "vendor_words": ["Chemicals", "Chem Industries", "Polymers", "Specialty Chemicals", "Organics"],
        "bases": [("Industrial Solvent", "litre", 140), ("Acetone", "litre", 110), ("Sulphuric Acid", "litre", 45),
                  ("Caustic Soda", "kg", 60), ("Epoxy Resin", "kg", 480), ("Paint Primer", "litre", 260),
                  ("Adhesive", "kg", 380), ("Water Treatment Chemical", "kg", 190), ("Coolant", "litre", 170),
                  ("Degreaser", "litre", 230)],
        "specs": ["Technical Grade", "Lab Grade", "AR Grade", "20L Drum", "50L Drum", "200L Drum",
                  "25kg Bag", "50kg Bag", "IBC Tank", "Industrial"],
    },
    "Office Supplies": {
        "n_vendors": 15, "n_items": 80, "po_share": 0.08, "lead_days": 5, "line_value": 20_000,
        "vendor_words": ["Stationers", "Office Supplies", "Paper Products", "Office Solutions", "Traders"],
        "bases": [("A4 Paper", "ream", 280), ("Printer Toner", "piece", 3200), ("Notebook", "piece", 60),
                  ("File Folder", "piece", 35), ("Pen Box", "box", 220), ("Stapler", "piece", 180),
                  ("Whiteboard Marker", "box", 300), ("Office Chair", "piece", 6500),
                  ("Desk Organiser", "piece", 450), ("Envelope", "box", 250)],
        "specs": ["Std", "Premium", "Economy", "Pack of 5", "Pack of 10", "Pack of 50", "Brand A", "Brand B"],
    },
}

PREFIXES = ["Sharma", "Gupta", "Patel", "Agarwal", "Mehta", "Reddy", "Iyer", "Singh", "Kapoor", "Jain",
            "Shah", "Verma", "Bansal", "Malhotra", "Desai", "Nair", "Rao", "Chopra", "Joshi", "Kulkarni",
            "Bharat", "Shree", "Apex", "Vardhman", "Sai", "Om", "Global", "Prime", "Supreme", "National",
            "Universal", "Royal", "Star", "Classic", "Allied", "United", "Pioneer", "Metro", "Galaxy",
            "Sunrise", "Ganesh", "Laxmi", "Krishna", "Balaji", "Hindustan", "Indo", "Eastern", "Western",
            "Southern", "Modern"]
SUFFIXES = ["Pvt Ltd", "Ltd", "Enterprises", "Industries", "LLP", "& Co"]
SUFFIX_P = [0.40, 0.15, 0.15, 0.15, 0.08, 0.07]

# (city, state, state code)
CITIES = [("Mumbai", "Maharashtra", "MH"), ("Pune", "Maharashtra", "MH"), ("Nagpur", "Maharashtra", "MH"),
          ("Ahmedabad", "Gujarat", "GJ"), ("Surat", "Gujarat", "GJ"), ("Chennai", "Tamil Nadu", "TN"),
          ("Coimbatore", "Tamil Nadu", "TN"), ("Bengaluru", "Karnataka", "KA"), ("Hyderabad", "Telangana", "TS"),
          ("Kolkata", "West Bengal", "WB"), ("Delhi", "Delhi", "DL"), ("Noida", "Uttar Pradesh", "UP"),
          ("Ghaziabad", "Uttar Pradesh", "UP"), ("Gurugram", "Haryana", "HR"), ("Faridabad", "Haryana", "HR"),
          ("Ludhiana", "Punjab", "PB"), ("Jaipur", "Rajasthan", "RJ"), ("Kochi", "Kerala", "KL"),
          ("Guwahati", "Assam", "AS"), ("Indore", "Madhya Pradesh", "MP")]
MONSOON_STATES = {"Maharashtra", "Kerala", "West Bengal", "Assam"}
STATE_CODES = {state: code for _, state, code in CITIES}

PAYMENT_TERMS = ["Net 15", "Net 30", "Net 45", "Net 60", "Advance"]
PAYMENT_P = [0.15, 0.40, 0.25, 0.12, 0.08]

# Order volume by month: Indian financial-year-end push in March, festive/Q4 peak, monsoon dip
MONTH_SEASON = {1: 0.95, 2: 0.95, 3: 1.25, 4: 0.90, 5: 0.95, 6: 0.90,
                7: 0.85, 8: 0.90, 9: 1.00, 10: 1.15, 11: 1.20, 12: 1.25}
ANNUAL_GROWTH = 1.10
PRICE_INFLATION = 1.05

ORDER_TYPES = ["Regular", "Bulk", "Urgent"]
ORDER_TYPE_P = [0.76, 0.14, 0.10]
LINES_PER_PO = [1, 2, 3, 4, 5]
LINES_PER_PO_P = [0.40, 0.25, 0.18, 0.10, 0.07]
N_BUYERS = 12


def random_date(start, end):
    return start + pd.Timedelta(days=int(rng.integers(0, (end - start).days + 1)))


def years_since_start(date):
    return (date - START).days / 365.25


# --------------------------------------------------------------------------------------
# Master data
# --------------------------------------------------------------------------------------
def make_vendors():
    rows, traits, used = [], [], set()
    for cat, cfg in CATEGORIES.items():
        n = cfg["n_vendors"]
        ranks = rng.permutation(n) + 1
        popularity = 1 / ranks ** 1.1
        popularity = popularity / popularity.sum() * cfg["po_share"]
        for i in range(n):
            while True:
                name = (f"{rng.choice(PREFIXES)} {rng.choice(cfg['vendor_words'])} "
                        f"{rng.choice(SUFFIXES, p=SUFFIX_P)}")
                if name not in used:
                    used.add(name)
                    break
            city, state, _ = CITIES[rng.integers(len(CITIES))]
            late_joiner = ranks[i] > 5 and rng.random() < 0.18
            onboarded = (random_date(pd.Timestamp("2023-01-01"), pd.Timestamp("2025-06-30")) if late_joiner
                         else random_date(pd.Timestamp("2012-01-01"), pd.Timestamp("2022-12-31")))
            vendor_id = f"V{len(rows) + 1:03d}"
            rows.append({"vendor_id": vendor_id, "vendor_name": name, "category": cat, "city": city,
                         "state": state, "onboarding_date": onboarded,
                         "payment_terms": rng.choice(PAYMENT_TERMS, p=PAYMENT_P)})

            poor_delivery = rng.random() < 0.15
            poor_quality = rng.random() < 0.10
            traits.append({
                "vendor_id": vendor_id,
                "category_rank": int(ranks[i]),
                "popularity": popularity[i],
                "on_time_prob": rng.uniform(0.45, 0.65) if poor_delivery else rng.uniform(0.70, 0.97),
                "avg_delay_days": rng.uniform(8, 20) if poor_delivery else rng.uniform(2, 12),
                "rejection_event_prob": rng.uniform(0.12, 0.25) if poor_quality else rng.uniform(0.01, 0.06),
                "price_factor": float(np.clip(rng.normal(1.0, 0.05), 0.88, 1.15)),
                "partial_ship_prob": rng.uniform(0.03, 0.15),
                "short_ship_prob": rng.uniform(0.0, 0.05),
                "poor_delivery": poor_delivery,
                "poor_quality": poor_quality,
                "monsoon_exposed": state in MONSOON_STATES,
                "declining_2025": False,
            })
    vendors, traits = pd.DataFrame(rows), pd.DataFrame(traits)

    # A few established, well-used vendors whose delivery performance slips in 2025
    candidates = traits.index[(traits["category_rank"] <= 10) & ~traits["poor_delivery"]
                              & (vendors["onboarding_date"] < START)]
    traits.loc[rng.choice(candidates, size=5, replace=False), "declining_2025"] = True
    return vendors, traits


def make_items():
    rows, traits = [], []
    for cat, cfg in CATEGORIES.items():
        combos = [(base, spec) for base in cfg["bases"] for spec in cfg["specs"]]
        for c in rng.choice(len(combos), size=cfg["n_items"], replace=False):
            (base, uom, base_price), spec = combos[c]
            std_price = round(base_price * rng.lognormal(0, 0.25), 2)
            item_id = f"I{len(rows) + 1:04d}"
            rows.append({"item_id": item_id, "item_name": f"{base} {spec}", "category": cat,
                         "unit_of_measure": uom, "standard_price": std_price})
            overstock = rng.random() < 0.20
            traits.append({
                "item_id": item_id,
                "popularity": rng.lognormal(0, 1),
                "typical_qty": max(1, round(cfg["line_value"] / std_price * rng.lognormal(0, 0.3))),
                "overstock": overstock,
                "declining_demand": overstock and rng.random() < 0.5,
            })
    return pd.DataFrame(rows), pd.DataFrame(traits)


def assign_approved_vendors(vendors, v_traits, items):
    """Each item gets 1-4 approved vendors from its category; ~18% are single-source."""
    item_vendors = []
    for cat in items["category"]:
        idx = np.flatnonzero(vendors["category"].to_numpy() == cat)
        w = v_traits["popularity"].to_numpy()[idx]
        k = 1 if rng.random() < 0.18 else int(rng.choice([2, 3, 4], p=[0.4, 0.4, 0.2]))
        item_vendors.append(list(rng.choice(idx, size=k, replace=False, p=w / w.sum())))

    # Every vendor must supply at least 5 items (never touching single-source items)
    vendor_items = {v: [] for v in range(len(vendors))}
    for i, vs in enumerate(item_vendors):
        for v in vs:
            vendor_items[v].append(i)
    for v, its in vendor_items.items():
        cat = vendors.at[v, "category"]
        pool = [i for i in np.flatnonzero(items["category"].to_numpy() == cat)
                if len(item_vendors[i]) > 1 and i not in its]
        for i in rng.choice(pool, size=max(0, 5 - len(its)), replace=False):
            item_vendors[i].append(v)
            its.append(i)
    return vendor_items


# --------------------------------------------------------------------------------------
# Transactions
# --------------------------------------------------------------------------------------
def make_purchase_orders(vendors, v_traits, items, i_traits, vendor_items):
    # Number of lines per PO, trimmed so the total is exactly N_PO_LINES
    n_lines = rng.choice(LINES_PER_PO, size=N_PO_LINES, p=LINES_PER_PO_P)
    n_pos = int(np.searchsorted(np.cumsum(n_lines), N_PO_LINES)) + 1
    n_lines = n_lines[:n_pos]
    n_lines[-1] -= n_lines.sum() - N_PO_LINES

    days = pd.date_range(START, END)
    day_w = (days.month.map(MONTH_SEASON).to_numpy()
             * ANNUAL_GROWTH ** ((days - START).days.to_numpy() / 365.25)
             * np.select([days.day_of_week == 6, days.day_of_week == 5], [0.0, 0.3], 1.0))
    po_dates = np.sort(rng.choice(days.to_numpy(), size=n_pos, p=day_w / day_w.sum()))

    v_pop = v_traits["popularity"].to_numpy()
    v_onboard = vendors["onboarding_date"].to_numpy()
    v_price = v_traits["price_factor"].to_numpy()
    i_pop = i_traits["popularity"].to_numpy()
    i_qty = i_traits["typical_qty"].to_numpy()
    i_price = items["standard_price"].to_numpy()

    cats = list(CATEGORIES)
    buyers = [f"B{b:02d}" for b in range(1, N_BUYERS + 1)]
    cat_buyers = {cat: list(rng.choice(buyers, size=3, replace=False)) for cat in cats}

    rows = []
    for p, (date, k) in enumerate(zip(po_dates, n_lines)):
        date = pd.Timestamp(date)
        w = v_pop * (v_onboard <= date.to_datetime64())
        v = int(rng.choice(len(w), p=w / w.sum()))
        cat = vendors.at[v, "category"]
        order_type = rng.choice(ORDER_TYPES, p=ORDER_TYPE_P)
        buyer = rng.choice(cat_buyers[cat])
        lead = CATEGORIES[cat]["lead_days"]
        inflation = PRICE_INFLATION ** years_since_start(date)

        its = vendor_items[v]
        iw = i_pop[its]
        for line, i in enumerate(rng.choice(its, size=k, replace=False, p=iw / iw.sum()), start=1):
            qty = i_qty[i] * rng.lognormal(0, 0.5)
            price = i_price[i] * v_price[v] * inflation * rng.normal(1, 0.02)
            if order_type == "Bulk":
                qty *= rng.uniform(4, 8)
                price *= rng.uniform(0.82, 0.92)
                promised = round(lead * rng.uniform(0.9, 1.4))
            elif order_type == "Urgent":
                qty *= rng.uniform(0.3, 0.8)
                price *= rng.uniform(1.05, 1.15)
                promised = max(2, round(lead * rng.uniform(0.3, 0.5)))
            else:
                promised = round(lead * rng.uniform(0.7, 1.3))
            rows.append({"po_id": f"PO{p + 1:06d}", "line_no": line, "order_date": date,
                         "vendor_id": vendors.at[v, "vendor_id"], "vendor_name": vendors.at[v, "vendor_name"],
                         "item_id": items.at[i, "item_id"], "quantity": max(1, int(round(qty))),
                         "unit_price": round(price, 2), "order_type": order_type,
                         "promised_date": date + pd.Timedelta(days=promised), "buyer_id": buyer})
    return pd.DataFrame(rows)


def make_deliveries(po, v_traits):
    t = v_traits.set_index("vendor_id")
    rows = []
    for r in po.itertuples(index=False):
        vt = t.loc[r.vendor_id]
        late_p = 1 - vt.on_time_prob
        if r.order_type == "Urgent":
            late_p += 0.10
        elif r.order_type == "Bulk":
            late_p += 0.05
        if vt.monsoon_exposed and r.promised_date.month in (6, 7, 8, 9):
            late_p += 0.15
        if vt.declining_2025 and r.order_date.year == 2025:
            late_p += 0.25

        if rng.random() < min(late_p, 0.95):
            offset = max(1, round(rng.gamma(2, vt.avg_delay_days / 2)))
        else:
            offset = -int(rng.integers(0, 4))
        # Early deliveries can never arrive before the order was placed
        first = max(r.promised_date + pd.Timedelta(days=offset), r.order_date + pd.Timedelta(days=1))

        u = rng.random()
        if u < vt.partial_ship_prob and r.quantity >= 2:
            q1 = max(1, int(r.quantity * rng.uniform(0.4, 0.8)))
            shipments = [(first, q1), (first + pd.Timedelta(days=int(rng.integers(5, 21))), r.quantity - q1)]
        elif u < vt.partial_ship_prob + vt.short_ship_prob:
            shipments = [(first, max(1, int(r.quantity * rng.uniform(0.7, 0.95))))]
        else:
            shipments = [(first, r.quantity)]

        for received, qty in shipments:
            if received > END:  # still in transit at the data cut-off -> open PO line
                continue
            rejected = 0
            if rng.random() < vt.rejection_event_prob:
                rejected = min(qty, max(1, round(qty * rng.uniform(0.02, 0.15))))
            rows.append({"po_id": r.po_id, "line_no": r.line_no, "received_date": received,
                         "qty_received": qty, "qty_rejected": rejected})

    dl = pd.DataFrame(rows).sort_values(["received_date", "po_id", "line_no"], ignore_index=True)
    dl.insert(0, "delivery_id", [f"DL{n:06d}" for n in range(1, len(dl) + 1)])
    return dl


def cap_to_available(planned, opening, receipts):
    """Consumption can't exceed stock on hand: unmet demand is carried to the next month (backorder)."""
    sold, stock, backlog = np.zeros_like(planned), opening, 0
    for t, (want, rec) in enumerate(zip(planned, receipts)):
        stock += rec
        want += backlog
        sold[t] = min(want, stock)
        backlog = want - sold[t]
        stock -= sold[t]
    return sold


def make_sales_and_inventory(items, i_traits, deliveries, po):
    """Monthly consumption per item, plus opening (2022-12-31) and closing (2025-12-31) stock."""
    months = pd.period_range(START, END, freq="M")
    acc = (deliveries.merge(po[["po_id", "line_no", "item_id"]], on=["po_id", "line_no"])
           .assign(acc=lambda d: d.qty_received - d.qty_rejected, month=lambda d: d.received_date.dt.to_period("M")))
    accepted = acc.groupby("item_id")["acc"].sum()
    accepted_by_month = acc.pivot_table(index="item_id", columns="month", values="acc", aggfunc="sum",
                                        fill_value=0).reindex(columns=months, fill_value=0)
    base_w = (months.month.map(MONTH_SEASON).to_numpy()
              * ANNUAL_GROWTH ** (np.arange(len(months)) / 12))

    sales, inventory = [], []
    for it, tr in zip(items.itertuples(index=False), i_traits.itertuples(index=False)):
        received = accepted.get(it.item_id, 0)
        if received == 0:
            # Never purchased in the period: old stock just sits there (dead stock)
            sold = np.zeros(len(months), dtype=int)
            opening = max(1, round(tr.typical_qty * rng.uniform(0.5, 2)))
        else:
            ratio = rng.uniform(0.45, 0.75) if tr.overstock else rng.uniform(0.93, 1.0)
            w = base_w * (np.linspace(1.3, 0.5, len(months)) if tr.declining_demand else 1)
            sold = np.round(received * ratio * w / w.sum() * rng.uniform(0.85, 1.15, len(months))).astype(int)
            opening = round(2 * sold.mean())
            sold = cap_to_available(sold, opening, accepted_by_month.loc[it.item_id].to_numpy())
        sales +=[{"item_id": it.item_id, "month": str(m), "qty_sold": int(s)} for m, s in zip(months, sold)]
        closing = max(0, opening + int(received) - int(sold.sum()))
        inventory += [{"item_id": it.item_id, "snapshot_date": pd.Timestamp("2022-12-31"), "qty_on_hand": opening},
                      {"item_id": it.item_id, "snapshot_date": END, "qty_on_hand": closing}]
    return pd.DataFrame(sales), pd.DataFrame(inventory)


# --------------------------------------------------------------------------------------
# Data-quality problems for the raw export
# --------------------------------------------------------------------------------------
def mask(n, frac):
    return rng.random(n) < frac


def mixed_dates(dates, p_dmy=0.20, p_mon=0.10):
    """ISO dates mixed with DD/MM/YYYY and D-Mon-YY, as when sheets from different teams are merged."""
    s = dates.dt.strftime("%Y-%m-%d")
    u = rng.random(len(dates))
    s = s.where(~(u < p_dmy), dates.dt.strftime("%d/%m/%Y"))
    s = s.where(~((u >= p_dmy) & (u < p_dmy + p_mon)),
                dates.dt.day.astype("Int64").astype(str) + "-" + dates.dt.strftime("%b-%y"))
    return s.fillna("")


def price_text(values, p_rupee=0.25):
    rupee = mask(len(values), p_rupee)
    return [("" if pd.isna(v) else f"₹{v:,.2f}" if r else f"{v:.2f}") for v, r in zip(values, rupee)]


def name_variant(name):
    options = [name.upper(), name.lower(), name + "  ", name.replace(" ", "  ", 1)]
    if name.endswith("Pvt Ltd"):
        options += [name.replace("Pvt Ltd", "Pvt. Ltd."), name.replace("Pvt Ltd", "Private Limited"),
                    name[: -len(" Pvt Ltd")]]
    elif name.endswith(" Ltd"):
        options += [name + ".", name.replace(" Ltd", " Limited")]
    elif name.endswith("& Co"):
        options += [name.replace("& Co", "and Co"), name.replace("& Co", "& Co.")]
    if "&" in name:
        options.append(name.replace("&", "and"))
    return options[rng.integers(len(options))]


def add_duplicates(df, frac, sort_by):
    dups = df.iloc[rng.choice(len(df), size=int(len(df) * frac), replace=False)]
    return pd.concat([df, dups]).sort_values(sort_by, kind="stable", ignore_index=True)


def messy_vendors(vendors, v_traits):
    raw = vendors.copy()
    raw["onboarding_date"] = mixed_dates(raw["onboarding_date"], p_dmy=0.15, p_mon=0.0)
    m = mask(len(raw), 0.12)
    raw.loc[m, "state"] = raw.loc[m, "state"].map(STATE_CODES)
    m = mask(len(raw), 0.06)
    raw.loc[m, "state"] = raw.loc[m, "state"].str.lower() + " "
    raw.loc[mask(len(raw), 0.04), "payment_terms"] = ""

    # Same supplier registered twice under a new code with a slightly different name
    originals = rng.choice(v_traits.index[v_traits["category_rank"] <= 8], size=5, replace=False)
    dup_rows, dup_map = [], {}
    for n, v in enumerate(originals, start=len(vendors) + 1):
        row = vendors.loc[v].copy()
        row["vendor_id"] = f"V{n:03d}"
        row["vendor_name"] = name_variant(row["vendor_name"])
        row["onboarding_date"] = random_date(pd.Timestamp("2023-01-01"), pd.Timestamp("2024-12-31")).strftime("%Y-%m-%d")
        dup_rows.append(row)
        dup_map[row["vendor_id"]] = vendors.at[v, "vendor_id"]
    raw = pd.concat([raw, pd.DataFrame(dup_rows)], ignore_index=True)
    return raw, dup_map, pd.DataFrame(dup_rows).set_index("vendor_id")["vendor_name"].to_dict()


def messy_items(items):
    raw = items.copy()
    raw["standard_price"] = price_text(raw["standard_price"], p_rupee=0.30)
    m = mask(len(raw), 0.06)
    raw.loc[m, "category"] = [rng.choice([c.upper(), c.lower(), c + " "]) for c in raw.loc[m, "category"]]
    raw.loc[mask(len(raw), 0.02), "unit_of_measure"] = ""
    return raw


def messy_purchase_orders(po, dup_map, dup_names):
    raw = po.copy()
    n = len(raw)

    # 30% of the POs of each duplicated vendor were raised against the duplicate code
    on_dup = np.zeros(n, dtype=bool)
    for dup_id, orig_id in dup_map.items():
        po_ids = raw.loc[raw["vendor_id"] == orig_id, "po_id"].unique()
        chosen = rng.choice(po_ids, size=int(len(po_ids) * 0.3), replace=False)
        m = raw["po_id"].isin(chosen).to_numpy()
        raw.loc[m, ["vendor_id", "vendor_name"]] = [dup_id, dup_names[dup_id]]
        on_dup |= m

    m = mask(n, 0.15) & ~on_dup
    raw.loc[m, "vendor_name"] = [name_variant(x) for x in raw.loc[m, "vendor_name"]]
    raw.loc[mask(n, 0.03), "vendor_id"] = ""

    m = mask(n, 0.10)
    raw.loc[m, "order_type"] = [rng.choice([t.upper(), t.lower(), t + " "]) for t in raw.loc[m, "order_type"]]

    prices = raw["unit_price"].to_numpy(dtype=float, copy=True)
    prices[mask(n, 0.003)] *= 100  # entered in paise instead of rupees
    prices[mask(n, 0.002)] = np.nan
    raw["unit_price"] = price_text(prices)

    m = mask(n, 0.003)
    raw.loc[m, "quantity"] = np.where(rng.random(m.sum()) < 0.5, 0, -raw.loc[m, "quantity"])

    raw.loc[mask(n, 0.004), "order_date"] = pd.NaT
    raw.loc[mask(n, 0.02), "promised_date"] = pd.NaT
    raw["order_date"] = mixed_dates(raw["order_date"])
    raw["promised_date"] = mixed_dates(raw["promised_date"])
    return add_duplicates(raw, 0.02, ["po_id", "line_no"])


def messy_deliveries(dl):
    raw = dl.copy()
    n = len(raw)
    m = mask(n, 0.003)  # wrong year typed in -> received before the order was placed
    raw.loc[m, "received_date"] = raw.loc[m, "received_date"] - pd.DateOffset(years=1)
    raw["received_date"] = mixed_dates(raw["received_date"])

    m = mask(n, 0.003)
    raw.loc[m, "qty_rejected"] = raw.loc[m, "qty_received"] + rng.integers(1, 20, m.sum())
    raw["qty_rejected"] = raw["qty_rejected"].astype("Int64").astype(str)
    raw.loc[mask(n, 0.01), "qty_rejected"] = ""

    m = mask(n, 0.002)  # receipts booked against PO numbers that do not exist
    raw.loc[m, "po_id"] = [f"PO{x:06d}" for x in rng.integers(900_000, 999_999, m.sum())]
    return add_duplicates(raw, 0.015, ["delivery_id"])


def messy_sales(sales):
    raw = sales.copy()
    m = mask(len(raw), 0.15)
    raw.loc[m, "month"] = pd.PeriodIndex(raw.loc[m, "month"], freq="M").strftime("%b-%Y")
    raw["qty_sold"] = raw["qty_sold"].astype(str)
    raw.loc[mask(len(raw), 0.005), "qty_sold"] = ""
    return add_duplicates(raw, 0.005, ["item_id"])


def messy_inventory(inventory):
    raw = inventory.copy()
    m = mask(len(raw), 0.005) & (raw["qty_on_hand"] > 0)
    raw.loc[m, "qty_on_hand"] = -raw.loc[m, "qty_on_hand"]
    raw["snapshot_date"] = raw["snapshot_date"].dt.strftime("%Y-%m-%d")
    return raw


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------
def summarise(vendors, items, po, dl, sales, inventory, v_traits, i_traits):
    po = po.assign(value=po.quantity * po.unit_price)
    spend = po.groupby("vendor_id")["value"].sum().sort_values(ascending=False)
    first = dl.sort_values("received_date").drop_duplicates(["po_id", "line_no"])
    first = first.merge(po[["po_id", "line_no", "promised_date", "order_type"]], on=["po_id", "line_no"])
    otd = (first.received_date <= first.promised_date).mean()
    rel_price = po.merge(items[["item_id", "standard_price"]], on="item_id").assign(
        rel=lambda d: d.unit_price / d.standard_price).groupby("order_type")["rel"].mean()
    vendors_per_item = po.groupby("item_id")["vendor_id"].nunique()
    closing = inventory[inventory.snapshot_date == END].merge(items, on="item_id")

    print("\n=== Ground-truth summary (what the analysis should rediscover) ===")
    print(f"PO lines: {len(po):,} | POs: {po.po_id.nunique():,} | deliveries: {len(dl):,}")
    print(f"Order dates: {po.order_date.min().date()} to {po.order_date.max().date()}")
    print(f"Total spend: INR {po.value.sum() / 1e7:,.1f} crore")
    print(f"Top-5 vendors share of spend: {spend.head(5).sum() / spend.sum():.1%} | "
          f"top-10: {spend.head(10).sum() / spend.sum():.1%}")
    print(f"On-time delivery (first shipment): {otd:.1%}")
    print(f"Avg price vs standard by order type: {rel_price.round(3).to_dict()}")
    print(f"Items purchased: {len(vendors_per_item)} of {len(items)} | "
          f"single-source among purchased: {(vendors_per_item == 1).mean():.1%}")
    print(f"Open (undelivered) PO lines: {len(po) - first.shape[0]:,}")
    print(f"Overstock items (planted): {int(i_traits.overstock.sum())} | "
          f"closing stock value: INR {(closing.qty_on_hand * closing.standard_price).sum() / 1e7:,.2f} crore")
    print(f"Poor-delivery vendors: {int(v_traits.poor_delivery.sum())} | "
          f"poor-quality vendors: {int(v_traits.poor_quality.sum())} | declining in 2025: "
          f"{int(v_traits.declining_2025.sum())}")


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    TRUTH_DIR.mkdir(parents=True, exist_ok=True)

    vendors, v_traits = make_vendors()
    items, i_traits = make_items()
    vendor_items = assign_approved_vendors(vendors, v_traits, items)
    po = make_purchase_orders(vendors, v_traits, items, i_traits, vendor_items)
    dl = make_deliveries(po, v_traits)
    sales, inventory = make_sales_and_inventory(items, i_traits, dl, po)

    truth = {"vendors": vendors, "items": items, "purchase_orders": po, "deliveries": dl,
             "sales": sales, "inventory": inventory, "vendor_traits": v_traits, "item_traits": i_traits}
    for name, df in truth.items():
        df.to_csv(TRUTH_DIR / f"{name}.csv", index=False, date_format="%Y-%m-%d")

    raw_vendors, dup_map, dup_names = messy_vendors(vendors, v_traits)
    raw = {"vendors": raw_vendors, "items": messy_items(items),
           "purchase_orders": messy_purchase_orders(po, dup_map, dup_names),
           "deliveries": messy_deliveries(dl), "sales": messy_sales(sales),
           "inventory": messy_inventory(inventory)}
    for name, df in raw.items():
        df.to_csv(RAW_DIR / f"{name}.csv", index=False, encoding="utf-8")
    (TRUTH_DIR / "duplicate_vendor_map.json").write_text(json.dumps(dup_map, indent=2))

    print("Rows written (raw / truth):")
    for name in raw:
        print(f"  {name:<16} {len(raw[name]):>7,} / {len(truth[name]):>7,}")
    summarise(vendors, items, po, dl, sales, inventory, v_traits, i_traits)


if __name__ == "__main__":
    main()
