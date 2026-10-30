-- =====================================================================================
-- Phase 5: procurement KPIs as SQL views (MariaDB 10.4+).
--
-- Layers:
--   v_*   building blocks: one row per PO line with receipts, flags and price benchmarks
--   kpi_* the KPIs, at different grains (overall, vendor, category, month, item)
--
-- Design decisions (from reports/eda_findings.md):
--   * Delivery KPIs judge every line whose promised date has passed by the data cut-off;
--     a due line with nothing received counts as LATE (avoids right-censoring bias).
--   * Price is benchmarked against the market (item median price in the same quarter and
--     order type), because standard costs are stale; standard-cost variance is reported too.
--   * Bulk savings and urgency premium are measured like-for-like against regular orders of
--     the same item from the same vendor in the same quarter (fallback: any vendor).
--   * Excess inventory = stock above 6 months of cover (based on the last 6 months of sales).
--
--   C:\xampp\mysql\bin\mysql.exe -u root --default-character-set=utf8mb4 procurement_db < sql/04_kpi_views.sql
-- =====================================================================================
SET NAMES utf8mb4;
USE procurement_db;

-- -------------------------------------------------------------------------------------
-- Building blocks
-- -------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_params AS
SELECT MAX(order_date) AS cutoff_date FROM purchase_orders;

-- One row per PO line that has at least one receipt
CREATE OR REPLACE VIEW v_line_receipts AS
SELECT d.po_id, d.line_no,
       MIN(d.received_date)                                                          AS first_received,
       MAX(d.received_date)                                                          AS last_received,
       COUNT(*)                                                                      AS shipments,
       SUM(d.qty_received)                                                           AS qty_received,
       SUM(CASE WHEN d.received_date <= p.promised_date THEN d.qty_received ELSE 0 END) AS qty_received_by_promise,
       SUM(d.qty_rejected)                                                           AS qty_rejected,
       SUM(CASE WHEN d.qty_rejected IS NOT NULL THEN d.qty_received END)             AS qty_inspected,
       SUM(d.qty_rejected > 0)                                                       AS receipts_with_rejection,
       SUM(d.qty_rejected IS NOT NULL)                                               AS receipts_inspected
FROM deliveries d
JOIN purchase_orders p USING (po_id, line_no)
GROUP BY d.po_id, d.line_no;

-- One row per PO line, enriched with master data, receipts and delivery flags
CREATE OR REPLACE VIEW v_po_lines AS
SELECT p.po_id, p.line_no, p.order_date, p.promised_date, p.order_type, p.buyer_id,
       p.vendor_id, v.vendor_name, v.state AS vendor_state,
       p.item_id, i.item_name, i.category, i.standard_price,
       p.quantity, p.unit_price, p.line_value,
       r.first_received, r.last_received,
       COALESCE(r.shipments, 0)                                   AS shipments,
       COALESCE(r.qty_received, 0)                                AS qty_received,
       COALESCE(r.qty_received_by_promise, 0)                     AS qty_received_by_promise,
       r.qty_rejected, r.qty_inspected, r.receipts_with_rejection, r.receipts_inspected,
       DATEDIFF(r.first_received, p.order_date)                   AS lead_time_days,
       DATEDIFF(r.first_received, p.promised_date)                AS delay_days,
       p.promised_date <= x.cutoff_date                           AS is_due,
       COALESCE(r.first_received <= p.promised_date, 0)           AS is_on_time,
       COALESCE(r.qty_received_by_promise, 0) >= p.quantity       AS is_otif,
       MONTH(p.promised_date) BETWEEN 6 AND 9                     AS is_monsoon_month,
       CASE WHEN r.first_received IS NULL THEN 'Open'
            WHEN r.qty_received < p.quantity THEN 'Partially received'
            ELSE 'Received' END                                   AS line_status
FROM purchase_orders p
JOIN items i USING (item_id)
LEFT JOIN vendors v USING (vendor_id)
LEFT JOIN v_line_receipts r USING (po_id, line_no)
CROSS JOIN v_params x;

-- Market price benchmarks per line (median price of the same item, quarter and order type)
CREATE OR REPLACE VIEW v_price_benchmark AS
SELECT po_id, line_no, item_id, vendor_id, order_type, order_date, quantity, unit_price, standard_price,
       CONCAT(YEAR(order_date), '-Q', QUARTER(order_date))                         AS quarter,
       MEDIAN(unit_price) OVER (PARTITION BY item_id, YEAR(order_date), QUARTER(order_date), order_type)
                                                                                   AS market_price,
       MEDIAN(unit_price) OVER (PARTITION BY item_id, vendor_id, YEAR(order_date), QUARTER(order_date), order_type)
                                                                                   AS vendor_quarter_price
FROM v_po_lines;

-- Bulk and urgent lines priced against regular orders: same item + vendor + quarter, else same item + quarter
CREATE OR REPLACE VIEW v_price_vs_regular AS
WITH reg_vendor AS (
    SELECT item_id, vendor_id, quarter, MAX(vendor_quarter_price) AS regular_price
    FROM v_price_benchmark WHERE order_type = 'Regular'
    GROUP BY item_id, vendor_id, quarter
), reg_market AS (
    SELECT item_id, quarter, MAX(market_price) AS regular_price
    FROM v_price_benchmark WHERE order_type = 'Regular'
    GROUP BY item_id, quarter
)
SELECT b.po_id, b.line_no, b.item_id, b.vendor_id, b.order_type, b.quarter, b.quantity, b.unit_price,
       COALESCE(rv.regular_price, rm.regular_price)                               AS regular_price,
       CASE WHEN rv.regular_price IS NOT NULL THEN 'same vendor'
            WHEN rm.regular_price IS NOT NULL THEN 'any vendor' END              AS benchmark,
       (b.unit_price - COALESCE(rv.regular_price, rm.regular_price)) * b.quantity AS diff_vs_regular
FROM v_price_benchmark b
LEFT JOIN reg_vendor rv ON rv.item_id = b.item_id AND rv.vendor_id = b.vendor_id AND rv.quarter = b.quarter
LEFT JOIN reg_market rm ON rm.item_id = b.item_id AND rm.quarter = b.quarter
WHERE b.order_type IN ('Bulk', 'Urgent');

-- -------------------------------------------------------------------------------------
-- KPI 1-9, 15: vendor scorecard (one row per vendor)
-- -------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW kpi_vendor_scorecard AS
WITH total AS (
    SELECT SUM(line_value) AS spend FROM purchase_orders
), price AS (
    SELECT vendor_id,
           SUM((unit_price - market_price) * quantity) / SUM(market_price * quantity) * 100 AS price_vs_market_pct
    FROM v_price_benchmark GROUP BY vendor_id
)
SELECT l.vendor_id,
       MAX(l.vendor_name)                                                         AS vendor_name,
       MAX(v.category)                                                            AS vendor_category,
       MAX(l.vendor_state)                                                        AS vendor_state,
       COUNT(*)                                                                   AS po_lines,
       SUM(l.line_value) / 1e7                                                    AS spend_crore,
       SUM(l.line_value) / MAX(t.spend) * 100                                     AS spend_share_pct,
       SUM(l.is_due)                                                              AS lines_due,
       AVG(CASE WHEN l.is_due THEN l.is_on_time END) * 100                        AS otd_pct,
       AVG(CASE WHEN l.is_due THEN l.is_otif END) * 100                           AS otif_pct,
       AVG(CASE WHEN l.is_due AND NOT l.is_monsoon_month THEN l.is_on_time END) * 100 AS otd_excl_monsoon_pct,
       AVG(CASE WHEN l.is_due AND YEAR(l.order_date) = YEAR(x.cutoff_date) - 1 THEN l.is_on_time END) * 100
                                                                                  AS otd_prev_year_pct,
       AVG(CASE WHEN l.is_due AND YEAR(l.order_date) = YEAR(x.cutoff_date) THEN l.is_on_time END) * 100
                                                                                  AS otd_last_year_pct,
       AVG(CASE WHEN l.delay_days > 0 THEN l.delay_days END)                      AS avg_delay_days,
       AVG(l.lead_time_days)                                                      AS avg_lead_time_days,
       STDDEV_SAMP(l.lead_time_days)                                              AS lead_time_sd_days,
       SUM(CASE WHEN l.is_due THEN LEAST(l.qty_received, l.quantity) END)
         / SUM(CASE WHEN l.is_due THEN l.quantity END) * 100                      AS fill_rate_pct,
       SUM(l.qty_rejected) / SUM(l.qty_inspected) * 100                           AS rejection_rate_pct,
       SUM(l.receipts_with_rejection) / SUM(l.receipts_inspected) * 100           AS receipts_with_rejection_pct,
       AVG(l.order_type = 'Urgent') * 100                                         AS urgent_order_pct,
       MAX(pr.price_vs_market_pct)                                                AS price_vs_market_pct
FROM v_po_lines l
JOIN vendors v ON v.vendor_id = l.vendor_id
CROSS JOIN total t
CROSS JOIN v_params x
LEFT JOIN price pr ON pr.vendor_id = l.vendor_id
GROUP BY l.vendor_id;

-- -------------------------------------------------------------------------------------
-- KPIs by category and by month (for trends and the dashboard)
-- -------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW kpi_category AS
SELECT category,
       COUNT(*)                                                                   AS po_lines,
       COUNT(DISTINCT vendor_id)                                                  AS vendors,
       SUM(line_value) / 1e7                                                      AS spend_crore,
       AVG(CASE WHEN is_due THEN is_on_time END) * 100                            AS otd_pct,
       AVG(CASE WHEN is_due THEN is_otif END) * 100                               AS otif_pct,
       AVG(lead_time_days)                                                        AS avg_lead_time_days,
       STDDEV_SAMP(lead_time_days)                                                AS lead_time_sd_days,
       SUM(CASE WHEN is_due THEN LEAST(qty_received, quantity) END)
         / SUM(CASE WHEN is_due THEN quantity END) * 100                          AS fill_rate_pct,
       SUM(qty_rejected) / SUM(qty_inspected) * 100                               AS rejection_rate_pct,
       AVG(order_type = 'Urgent') * 100                                           AS urgent_order_pct,
       SUM((unit_price - standard_price) * quantity) / SUM(standard_price * quantity) * 100
                                                                                  AS price_vs_standard_pct
FROM v_po_lines
GROUP BY category;

CREATE OR REPLACE VIEW kpi_monthly AS
WITH ordered AS (
    SELECT DATE_FORMAT(order_date, '%Y-%m-01') AS month,
           COUNT(*) AS po_lines, SUM(line_value) / 1e7 AS spend_crore,
           AVG(order_type = 'Urgent') * 100 AS urgent_order_pct,
           AVG(order_type = 'Bulk') * 100 AS bulk_order_pct
    FROM v_po_lines GROUP BY month
), due AS (
    SELECT DATE_FORMAT(promised_date, '%Y-%m-01') AS month,
           COUNT(*) AS lines_due,
           AVG(is_on_time) * 100 AS otd_pct,
           AVG(is_otif) * 100 AS otif_pct,
           SUM(LEAST(qty_received, quantity)) / SUM(quantity) * 100 AS fill_rate_pct
    FROM v_po_lines WHERE is_due GROUP BY month
), received AS (
    SELECT DATE_FORMAT(d.received_date, '%Y-%m-01') AS month,
           SUM(d.qty_rejected) / SUM(CASE WHEN d.qty_rejected IS NOT NULL THEN d.qty_received END) * 100
               AS rejection_rate_pct
    FROM deliveries d GROUP BY month
)
SELECT o.month, o.po_lines, o.spend_crore, o.urgent_order_pct, o.bulk_order_pct,
       d.lines_due, d.otd_pct, d.otif_pct, d.fill_rate_pct, r.rejection_rate_pct
FROM ordered o
LEFT JOIN due d USING (month)
LEFT JOIN received r USING (month);

-- -------------------------------------------------------------------------------------
-- KPI 10-11: spend concentration and single-source items
-- -------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW kpi_concentration AS
WITH vendor_spend AS (
    SELECT vendor_id, SUM(line_value) AS spend FROM purchase_orders GROUP BY vendor_id
), ranked AS (
    SELECT spend,
           spend / SUM(spend) OVER ()                                              AS share,
           ROW_NUMBER() OVER (ORDER BY spend DESC)                                 AS rk,
           SUM(spend) OVER (ORDER BY spend DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
             / SUM(spend) OVER ()                                                  AS cum_share
    FROM vendor_spend
)
SELECT COUNT(*)                                     AS active_vendors,
       MAX(CASE WHEN rk = 1 THEN share END) * 100   AS top1_share_pct,
       SUM(CASE WHEN rk <= 5 THEN share END) * 100  AS top5_share_pct,
       SUM(CASE WHEN rk <= 10 THEN share END) * 100 AS top10_share_pct,
       SUM(cum_share < 0.8) + 1                     AS vendors_for_80pct_spend,
       SUM(share * share) * 10000                   AS hhi
FROM ranked;

CREATE OR REPLACE VIEW kpi_single_source_items AS
SELECT p.item_id, i.item_name, i.category,
       MIN(p.vendor_id)          AS only_vendor,
       COUNT(*)                  AS po_lines,
       SUM(p.line_value) / 1e7   AS spend_crore
FROM purchase_orders p
JOIN items i USING (item_id)
GROUP BY p.item_id, i.item_name, i.category
HAVING COUNT(DISTINCT p.vendor_id) = 1;

-- -------------------------------------------------------------------------------------
-- KPI 12-13: inventory (per item)
-- Stock at the previous year-end is rebuilt from the opening snapshot plus accepted
-- receipts minus sales; the same rebuild for the closing date is a reconciliation check.
-- -------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW kpi_inventory_items AS
WITH snaps AS (
    SELECT MIN(snapshot_date) AS opening_date, MAX(snapshot_date) AS closing_date FROM inventory
), accepted AS (
    SELECT p.item_id,
           SUM(CASE WHEN d.received_date <= DATE_SUB(x.cutoff_date, INTERVAL 1 YEAR)
                    THEN d.qty_received - COALESCE(d.qty_rejected, 0) END)        AS acc_to_prev_year_end,
           SUM(d.qty_received - COALESCE(d.qty_rejected, 0))                      AS acc_total
    FROM deliveries d
    JOIN purchase_orders p USING (po_id, line_no)
    CROSS JOIN v_params x
    GROUP BY p.item_id
), sold AS (
    SELECT s.item_id,
           SUM(CASE WHEN s.month <= DATE_SUB(x.cutoff_date, INTERVAL 1 YEAR) THEN s.qty_sold END) AS sold_to_prev_year_end,
           SUM(s.qty_sold)                                                        AS sold_total,
           SUM(CASE WHEN YEAR(s.month) = YEAR(x.cutoff_date) THEN s.qty_sold END) AS sold_last_year,
           AVG(CASE WHEN s.month > DATE_SUB(x.cutoff_date, INTERVAL 6 MONTH) THEN s.qty_sold END)
                                                                                  AS avg_monthly_sales_6m
    FROM sales s CROSS JOIN v_params x
    GROUP BY s.item_id
)
SELECT i.item_id, i.item_name, i.category, i.standard_price,
       o.qty_on_hand                                                              AS opening_qty,
       -- floored at 0: a few items rebuild slightly negative because some receipts could not be
       -- linked to a PO during cleaning (see notebooks/03_kpis.ipynb, reconciliation check)
       GREATEST(o.qty_on_hand + COALESCE(a.acc_to_prev_year_end, 0) - COALESCE(s.sold_to_prev_year_end, 0), 0)
                                                                                  AS prev_year_end_qty,
       c.qty_on_hand                                                              AS closing_qty,
       o.qty_on_hand + COALESCE(a.acc_total, 0) - COALESCE(s.sold_total, 0)       AS closing_qty_rebuilt,
       s.sold_last_year,
       s.avg_monthly_sales_6m,
       c.qty_on_hand / NULLIF(s.avg_monthly_sales_6m, 0)                          AS months_of_cover,
       c.qty_on_hand * i.standard_price                                           AS closing_value,
       GREATEST(c.qty_on_hand - 6 * COALESCE(s.avg_monthly_sales_6m, 0), 0)       AS excess_qty,
       GREATEST(c.qty_on_hand - 6 * COALESCE(s.avg_monthly_sales_6m, 0), 0) * i.standard_price
                                                                                  AS excess_value
FROM items i
CROSS JOIN snaps sn
JOIN inventory o ON o.item_id = i.item_id AND o.snapshot_date = sn.opening_date
JOIN inventory c ON c.item_id = i.item_id AND c.snapshot_date = sn.closing_date
LEFT JOIN accepted a ON a.item_id = i.item_id
LEFT JOIN sold s     ON s.item_id = i.item_id;

-- -------------------------------------------------------------------------------------
-- KPI summary: one row per headline KPI (feeds the dashboard cards and the README)
-- -------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW kpi_summary AS
WITH l AS (
    SELECT
        SUM(line_value)                                                            AS spend,
        COUNT(*)                                                                   AS n_lines,
        AVG(CASE WHEN is_due THEN is_on_time END) * 100                            AS otd,
        AVG(CASE WHEN is_due THEN is_otif END) * 100                               AS otif,
        AVG(CASE WHEN delay_days > 0 THEN delay_days END)                          AS avg_delay,
        AVG(lead_time_days)                                                        AS lead,
        STDDEV_SAMP(lead_time_days)                                                AS lead_sd,
        SUM(CASE WHEN is_due THEN LEAST(qty_received, quantity) END)
          / SUM(CASE WHEN is_due THEN quantity END) * 100                          AS fill,
        SUM(qty_rejected) / SUM(qty_inspected) * 100                               AS rej,
        SUM(receipts_with_rejection) / SUM(receipts_inspected) * 100               AS rej_receipts,
        SUM((unit_price - standard_price) * quantity) / SUM(standard_price * quantity) * 100 AS ppv_std,
        AVG(order_type = 'Urgent') * 100                                           AS urgent,
        SUM(is_due AND first_received IS NULL)                                     AS overdue_open
    FROM v_po_lines
), pv AS (
    SELECT -SUM(CASE WHEN order_type = 'Bulk' THEN diff_vs_regular END)            AS bulk_savings,
           -SUM(CASE WHEN order_type = 'Bulk' THEN diff_vs_regular END)
             / SUM(CASE WHEN order_type = 'Bulk' THEN regular_price * quantity END) * 100 AS bulk_discount,
           SUM(CASE WHEN order_type = 'Urgent' THEN diff_vs_regular END)           AS urgent_premium
    FROM v_price_vs_regular
), ss AS (
    SELECT COUNT(*) AS n, SUM(spend_crore) AS spend_cr FROM kpi_single_source_items
), items_bought AS (
    SELECT COUNT(DISTINCT item_id) AS n FROM purchase_orders
), inv AS (
    SELECT SUM(closing_value) AS closing_value,
           SUM(excess_value) AS excess_value,
           SUM(sold_last_year * standard_price) AS cogs,
           SUM((prev_year_end_qty + closing_qty) / 2 * standard_price) AS avg_inventory_value
    FROM kpi_inventory_items
)
SELECT  1 AS kpi_no, 'On-time delivery (OTD)' AS kpi, ROUND(l.otd, 2) AS value, '%' AS unit,
        'Share of PO lines due by the cut-off whose first receipt arrived on or before the promised date (overdue open lines count as late)' AS definition
FROM l
UNION ALL SELECT  2, 'On-time in full (OTIF)', ROUND(l.otif, 2), '%',
        'Share of due PO lines where the full ordered quantity was received by the promised date' FROM l
UNION ALL SELECT  3, 'Average delay of late deliveries', ROUND(l.avg_delay, 2), 'days',
        'Mean days between promised date and first receipt, late lines only' FROM l
UNION ALL SELECT  4, 'Average lead time', ROUND(l.lead, 2), 'days',
        'Mean days from order date to first receipt' FROM l
UNION ALL SELECT  5, 'Lead-time variability', ROUND(l.lead_sd, 2), 'days',
        'Standard deviation of lead time across PO lines' FROM l
UNION ALL SELECT  6, 'Fill rate', ROUND(l.fill, 2), '%',
        'Quantity received (capped at ordered) / quantity ordered, due lines' FROM l
UNION ALL SELECT  7, 'Rejection rate (quantity)', ROUND(l.rej, 3), '%',
        'Quantity rejected at inspection / quantity inspected' FROM l
UNION ALL SELECT  8, 'Receipts with rejections', ROUND(l.rej_receipts, 2), '%',
        'Share of goods receipts with at least one rejected unit' FROM l
UNION ALL SELECT  9, 'Purchase price variance vs standard cost', ROUND(l.ppv_std, 2), '%',
        'Sum((unit price - standard price) x qty) / sum(standard price x qty)' FROM l
UNION ALL SELECT 10, 'Total spend', ROUND(l.spend / 1e7, 2), '₹ crore',
        'Sum of PO line values' FROM l
UNION ALL SELECT 11, 'Top vendor share of spend', ROUND(c.top1_share_pct, 2), '%',
        'Spend with the largest vendor / total spend' FROM kpi_concentration c
UNION ALL SELECT 12, 'Top-5 vendor share of spend', ROUND(c.top5_share_pct, 2), '%',
        'Spend with the 5 largest vendors / total spend' FROM kpi_concentration c
UNION ALL SELECT 13, 'Vendor concentration (HHI)', ROUND(c.hhi, 0), 'index',
        'Herfindahl-Hirschman index of vendor spend shares (0-10,000; >1,500 = concentrated)' FROM kpi_concentration c
UNION ALL SELECT 14, 'Vendors making up 80% of spend', c.vendors_for_80pct_spend, 'vendors',
        'Smallest number of vendors whose spend reaches 80% of the total' FROM kpi_concentration c
UNION ALL SELECT 15, 'Single-source items', ROUND(ss.n / ib.n * 100, 2), '%',
        'Items bought from only one vendor / items bought' FROM ss CROSS JOIN items_bought ib
UNION ALL SELECT 16, 'Bulk-buy savings realised', ROUND(pv.bulk_savings / 1e7, 2), '₹ crore',
        'Sum over bulk lines of (regular price - bulk price) x qty, like-for-like' FROM pv
UNION ALL SELECT 17, 'Bulk discount vs regular price', ROUND(pv.bulk_discount, 2), '%',
        'Bulk-buy savings / value of bulk lines at regular prices' FROM pv
UNION ALL SELECT 18, 'Urgent-order premium paid', ROUND(pv.urgent_premium / 1e7, 2), '₹ crore',
        'Sum over urgent lines of (urgent price - regular price) x qty, like-for-like' FROM pv
UNION ALL SELECT 19, 'Urgent orders', ROUND(l.urgent, 2), '%',
        'Share of PO lines raised as urgent' FROM l
UNION ALL SELECT 20, 'Excess inventory value', ROUND(inv.excess_value / 1e7, 2), '₹ crore',
        'Value (standard cost) of stock above 6 months of cover' FROM inv
UNION ALL SELECT 21, 'Excess inventory share of stock', ROUND(inv.excess_value / inv.closing_value * 100, 2), '%',
        'Excess inventory value / closing stock value' FROM inv
UNION ALL SELECT 22, 'Inventory turnover', ROUND(inv.cogs / inv.avg_inventory_value, 2), 'times/year',
        'Last-year consumption at standard cost / average inventory value' FROM inv
UNION ALL SELECT 23, 'Days of inventory on hand', ROUND(365 / (inv.cogs / inv.avg_inventory_value), 1), 'days',
        '365 / inventory turnover' FROM inv
UNION ALL SELECT 24, 'Overdue open PO lines', l.overdue_open, 'lines',
        'PO lines past their promised date with nothing received' FROM l;
