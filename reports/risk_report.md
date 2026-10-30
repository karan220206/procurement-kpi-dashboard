# Risk Analytics Report

Sources: `notebooks/04_risk_score.ipynb` (vendor risk score, re-sourcing scenario) and `notebooks/05_delay_model.ipynb`
(late-delivery prediction). Outputs: `procurement_db.vendor_risk_scores`, `procurement_db.po_line_late_risk`, and the
files in `reports/risk/`. Charts are figures 18–23 in `reports/figures/`.

---

## 1. Vendor risk score (0–100)

**Method**
- The score combines eight components:
  - **Performance (80%):** delivery 25%, quality 20%, delay severity 10%, lead-time variability 10%, deterioration vs the previous year 10%, price premium vs market 5%.
  - **Exposure (20%):** share of the vendor's category spend 15%, single-source items 5%.
- Each component is scaled between the 5th and 95th percentile across vendors.

**Tiers**
- **High:** score ≥ 50, or a red flag (worst ~5–10% on delivery, quality or deterioration).
- **Medium:** score 35–50.
- **Low:** score below 35.

### Results

| Tier | Vendors | Spend | Share of spend |
|---|---:|---:|---:|
| **High** | **38** | ₹701 cr | **45.5%** |
| Medium | 31 | ₹281 cr | 18.2% |
| Low | 79 | ₹558 cr | 36.2% |
| Insufficient data (< 30 lines due) | 2 | ₹0.3 cr | 0.0% |

- **Highest scores:**
  - **V102** Global Industrial Services: 77, very poor delivery
  - **V047** Modern Pack Solutions: 70
  - **V106** Agarwal Systems: 69, ₹64 cr spend, 49% on-time
- **V017 United Ispat** (₹289 cr, the largest vendor) is High because of **dependency**, not performance. It supplies 32% of Raw Materials. The action here is to *diversify*, not to drop the vendor.
- **30 vendors carry a red flag.** 18 of them are High only because of the flag. Without it, severe single issues (e.g. V061's 24% rejection rate) would be averaged away.

### Is it robust?
- **Rank correlation with alternative weightings:** 0.90 (equal weights) and 0.98 (delivery-heavy).
- **8 of the top 10 vendors** stay in the top 10 under both alternatives.

### Simulation check (synthetic data only)
The data generator planted 38 problem vendors. The score never sees these labels.

| | Result |
|---|---|
| Planted problem vendors scored High | **30 of 38** |
| Planted problem vendors scored High or Medium | 36 of 38 |
| Vendors with no planted problem scored High (false alarms) | 8 of 110 |

---

## 2. Scenario: re-source the 10 largest High-risk vendors

**Rules**
- 2025 volume of the 10 High-risk vendors with the most spend (₹213 cr, 5,303 lines) is moved to alternatives.
- An alternative must have supplied **the same item** before.
- It must be in the Low or Medium tier.
- It must be **at least as punctual** as the current vendor.
- It can take at most **+50%** of its own volume.

Under these rules, **₹101.9 cr (48%) could be moved**, across 1,773 lines and 83 alternative vendors.

| Measure | Now | After re-sourcing | Change |
|---|---:|---:|---:|
| On-time delivery, re-sourced lines | 59.1% | **79.1%** | **+20.0 pp** |
| Average lead time, re-sourced lines | 16.1 days | **11.2 days** | **−31%** |
| On-time delivery, all 2025 lines | 70.9% | 72.8% | +1.9 pp |
| Average lead time, all 2025 lines | 12.2 days | 11.7 days | −4% |
| Late lines avoided (expected) | | ~342 | |
| Price impact | | | **−₹1.25 cr** (alternatives are slightly cheaper) |

**Caveats**
- Expected values use each vendor's historical on-time rate and lead time.
- Alternatives may perform worse under extra load, so the +50% capacity cap is an assumption to confirm with the vendors.
- Switching costs are not included: qualification, contract changes, logistics.

---

## 3. Predicting late deliveries

**Set-up**
- Features are known at order time: order type, category, size, promised lead time, monsoon timing, and the vendor's track record up to the order date (using only outcomes already known by then).
- Time-based split: train on 2023–2024 orders (31,714 lines), test on 2025 orders (17,596 lines, 29.1% late).

| Model | ROC-AUC | PR-AUC | Late lines caught in riskiest 20% | Precision in riskiest 20% |
|---|---:|---:|---:|---:|
| Baseline: vendor's past late rate | 0.659 | 0.417 | 32.1% | 46.7% |
| **Logistic regression** | **0.674** | **0.441** | **32.6%** | **47.4%** |
| Random forest | 0.671 | 0.432 | 31.9% | 46.4% |

- **How high could it go?** Late deliveries in this data are random draws from known probabilities. Scoring with the *true* probabilities gives AUC **0.690**, the best any model could achieve here. The logistic regression reaches **92% of the achievable gain** over random guessing.
- **Risk ranking works.** The safest decile of lines is late 9% of the time; the riskiest decile is late **51%** of the time (5.5×).
- **Drivers** (permutation importance):
  - the vendor's past late rate (dominant)
  - monsoon month × monsoon-state vendor
  - order type (urgent orders are later)
  - the vendor's recent (180-day) late rate

  Quantity, value and category add almost nothing.
- **Honest read:** most of the signal is simply the vendor's track record. The model adds monsoon timing and order type on top. That makes the vendor risk score above the main tool, with the model as an order-level early warning.

**Early-warning list:** the 661 PO lines not yet due at the cut-off were scored.
- **28 are High risk** (≥ 50% chance of being late, ₹1.3 cr).
- 205 are Medium.
- They are stored in `po_line_late_risk` for buyers to expedite.

---

## Recommendations

1. **Re-source or put on improvement plans the 10 largest High-risk vendors.** On the volume that can move, on-time delivery could rise from 59% to 79% and lead time could fall by 31%.
2. **Diversify Raw Materials away from V017** (32% of the category), even though its performance is average.
3. **Plan for the monsoon.** For vendors in Assam, West Bengal, Maharashtra and Kerala, add about 1–2 weeks of buffer, or shift volume, for June–September deliveries.
4. **Act on V061's quality** (24% of receipts with rejections, ₹28 cr spend): run a supplier quality audit.
5. **Use the early-warning list each week** to chase the riskiest open PO lines before they are late.
