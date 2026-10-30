# Vendor KPI Report (Jan 2023 – Dec 2025)

**How the KPIs are built:**
- 24 KPIs are defined as SQL views in `sql/04_kpi_views.sql`.
- Every KPI was recomputed independently in pandas from the base tables (`notebooks/03_kpis.ipynb`), and **all 24 match**.
- The exported tables are in `reports/kpi/`.

## Headline KPIs

| # | KPI | Value | What it says |
|---|---|---:|---|
| 1 | On-time delivery (OTD) | **71.0%** | About 3 in 10 PO lines arrive late |
| 2 | On-time in full (OTIF) | **62.6%** | A further 8 points arrive on time but short |
| 3 | Average delay of late deliveries | 10.6 days | Median 7 days; 10% are over 3 weeks late |
| 4–5 | Lead time (mean ± std dev) | 12.3 ± 8.7 days | Large variability, so planners need big buffers |
| 6 | Fill rate | 98.9% | Quantities do eventually arrive: the problem is **timing**, not volume |
| 7 | Rejection rate (quantity) | 0.35% | Low overall… |
| 8 | Receipts with rejections | 4.5% | …but concentrated in a few vendors (below) |
| 9 | Price variance vs standard cost | +4.2% | Standards are stale; Raw Materials is at +6.8% |
| 10 | Total spend | ₹1,540 crore | |
| 11–12 | Top vendor / top-5 vendor share | **18.7% / 39.3%** | One vendor (V017) supplies 32% of Raw Materials spend |
| 13 | HHI | 537 | Low overall because spend spans 7 categories. Dependency shows up within categories, not across them |
| 14 | Vendors making up 80% of spend | 38 of 150 | |
| 15 | Single-source items | 19.0% | 151 items have one supplier only |
| 16–17 | Bulk-buy savings realised | **₹104.4 crore** (13.1% discount) | Bulk buying works when used |
| 18–19 | Urgent-order premium | ₹5.2 crore on 9.8% of lines | Paid for poor planning |
| 20–21 | Excess inventory | **₹99.3 crore (43.5% of stock)** | Stock above 6 months of cover |
| 22–23 | Inventory turnover | 2.41× / 152 days on hand | |
| 24 | Overdue open PO lines | 289 | Current backlog |

## What the KPIs show

**1. Delivery reliability is the biggest problem, and it is not improving.**
- OTD has been flat for three years: 70.8%, 71.1% and 71.0%.
- OTIF is 62.6%, while the eventual fill rate is 98.9%. So vendors do ship the quantity; they ship it late.

**2. A watch list of 37 vendors.**
- These vendors are below 65% on-time or have rejections on more than 10% of their receipts.
- They hold **29% of spend**.
- The largest, all with a lot of spend and poor delivery:

  | Vendor | Spend | On-time | Note |
  |---|---|---|---|
  | V070 Patel Electronics | ₹69 cr | 60% | |
  | V016 Om Ispat | ₹67 cr | 63% | |
  | V106 Agarwal Systems | ₹64 cr | 49% | Average delay 21 days |

- Quality is the problem at **V061 Pioneer Electricals** (₹28 cr): 24% of its receipts have rejections, against a 4.5% average.

**3. Dependency sits inside categories.**
- V017 United Ispat alone is 18.7% of all spend and 32% of Raw Materials.
- Its delivery is average (71% OTD, 59% OTIF). A disruption there would hit the largest category directly.

**4. Bulk buying saves money; urgent buying costs money.**
- Realised bulk savings are ₹104 crore at a 13% like-for-like discount.
- Urgent orders, about 10% of lines, carried a ₹5.2 crore premium. Each urgent order replaced by planned buying recovers about 10% of its price.

**5. Working capital is tied up in excess stock.**
- ₹99 crore (43.5% of stock value) sits above 6 months of cover.
- It is concentrated in Raw Materials (₹57 crore), e.g. CR coil and steel billet items holding 2–5 years of stock.
- Turnover is 2.4× a year (152 days on hand).

## Data checks behind these numbers
- **SQL vs pandas:** 24 of 24 KPIs identical (`reports/kpi/kpi_sql_vs_pandas_check.csv`).
- **Stock reconciliation:** opening stock + accepted receipts − sales equals closing stock exactly for 73% of items. The gaps trace to the ~2% of records that cleaning had to drop or estimate (net 1.4% of closing units). Rebuilt stock used for turnover is floored at zero.
- **Right-censoring handled:** overdue undelivered lines count as late; lines not yet due are excluded.

## Exported tables (`reports/kpi/`)
- `kpi_summary.csv` (24 KPIs)
- `kpi_vendor_scorecard.csv` (150 vendors × 20 metrics)
- `kpi_category.csv`
- `kpi_monthly.csv`
- `kpi_inventory_items.csv`
- `kpi_single_source_items.csv`
- `kpi_sql_vs_pandas_check.csv`
