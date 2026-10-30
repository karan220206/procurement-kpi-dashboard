# EDA Findings — Procurement Data (Jan 2023 – Dec 2025)

Source: `notebooks/02_eda.ipynb` on the clean tables in `procurement_db`. Charts are in `reports/figures/`.
Scope: 49,971 PO lines · 22,707 purchase orders · 150 vendors · 797 items bought · **₹1,540 crore** total spend.

## Key findings

**1. Spend is growing faster than order volume, so prices are rising.**
Spend grew **+27%** in 2024 and **+12%** in 2025, while PO lines grew only +15% and +8%.
Regular-order prices went from 4% above standard cost in 2023 to **15% above in 2025**.
*(Figure 01)*

**2. Ordering is seasonal: peaks in March and October–December.**
December runs **+31%** above an average month, October +23%, March +16% (financial-year-end) and November +15%.
April to July are the quietest months (−16% to −18%). *(Figure 02)*

**3. Spend is highly concentrated, so vendor dependency is real.**
- Raw Materials is **58%** of all spend (₹896 cr).
- One vendor, **V017 United Ispat LLP, takes 18.7% of total spend** (₹289 cr).
- The top 5 vendors take **39%**, the top 10 take **52%**, and **38 of 150 vendors** make up 80% of spend.
- **151 items (19%) are single-source**, but they carry only 7% of spend. The dependency risk sits more in large vendors than in single-source items.
*(Figures 03, 04)*

**4. Bulk buying saves about 13%; urgent orders cost about 10% extra.**
- Like-for-like (same item, same vendor, same quarter), bulk prices are **13.1% lower** than regular, with the middle half of cases between 10.7% and 15.4%.
- Urgent orders are priced a median **20.7%** above standard cost, against 9.7% for regular orders. That is an urgency premium of about 10 points.
*(Figure 08)*

**5. Lead times depend on category: a median of 4 days for office supplies, 19 days for IT hardware.**
Raw Materials take a median of 14 days, and a long tail runs past 60 days in every category. *(Figure 07)*

**6. Only 71% of PO lines arrive on time.**
- **71.0%** of PO lines due by the cut-off arrived on or before the promised date.
- Late lines are a median **7 days** late, and 10% are more than **23 days** late.
*(Figure 09)*

**7. Monsoon months hit four states hard.**
- Vendors in **Assam, West Bengal, Maharashtra and Kerala** have a late rate **14–17 points higher** in June–September.
- On-time delivery for these states falls from about 75% to **55–62%** every monsoon. Other states hold steady around 70–73%.
*(Figures 10, 11)*

**8. A few vendors drive most of the lateness, and some are getting worse.**
- **27 of 148 vendors** deliver on time less than 65% of the time. They form a distinct low tail. *(Figure 13)*
- **5 vendors slipped by more than 15 points in 2025:**

  | Vendor | 2025 on-time | Change vs 2024 |
  |---|---|---|
  | V034 | 48% | −33 pp |
  | V079 | 55% | −25 pp |
  | V014 Shree Ispat, a large raw-materials supplier | 69% | −23 pp |
  | V118 | 40% | −23 pp |
  | V094 | 77% | −17 pp |

  These vendors are early-warning cases for the risk score. *(Figure 12)*

**9. Quality problems are concentrated in a few vendors.**
- Overall, only **0.35%** of received quantity is rejected.
- About **9 vendors** have rejections on **10–35% of their receipts**. A typical vendor is at 1–6%.

  The worst are **V110, V061, V092, V089 and V150**. V061 matters most because it is a high-volume vendor. *(Figure 14)*

**10. Excess inventory: 21% of items hold 56% of stock value.**
- Closing stock is **₹228.5 crore** at standard cost, and the median item holds 3.0 months of cover.
- **167 items (21%) have more than 6 months of cover**. They hold **₹128 crore, which is 56% of all stock value**.
- The distribution is clearly split in two. No item sits between 6 and 11 months, so "over 6 months of cover" separates normal stock from excess stock cleanly.
- 7 items had no sales at all in H2 2025 (dead stock).
*(Figure 15)*

**11. The cleaned data is reliable for analysis.**
93.5% of PO lines needed no fix. Only 2.3% of lines (2.25% of spend) contain an imputed value, so imputation cannot drive any KPI.

## What this means for Phase 5 (KPI design)

| Finding | KPI design decision |
|---|---|
| Right-censoring at the cut-off (late lines not yet received) | On-time KPIs count **overdue open lines as late** and exclude lines not yet due |
| Standard costs are stale (regular prices +15% over standard by 2025) | Price variance is measured against a **market benchmark** (item median price that quarter), with standard-cost variance reported separately |
| Bulk vs regular prices differ by item mix | Bulk-buy savings measured **like-for-like** (same item, vendor and quarter) |
| Excess stock splits clearly at 6 months of cover | Excess-inventory KPI = value of stock above **6 months of cover** |
| Strong monsoon effect for 4 states | Vendor scorecards show on-time **with and without Jun–Sep**, so vendors aren't penalised for weather alone |
| Some vendors are deteriorating | The risk score includes a **trend component** (change vs prior year), not just levels |
