-- =====================================================================================
-- Data-quality checks on the staging tables, in SQL.
-- These mirror src/profile_raw.py, which computes the same counts in pandas
-- (counts here are on raw rows, before duplicates are removed).
--   C:\xampp\mysql\bin\mysql.exe -u root --table procurement_db < sql/02_staging_checks.sql
-- =====================================================================================
SET NAMES utf8mb4;

-- 1. Row counts per staging table
SELECT 'stg_vendors' AS tbl, COUNT(*) AS n_rows FROM stg_vendors
UNION ALL SELECT 'stg_items', COUNT(*) FROM stg_items
UNION ALL SELECT 'stg_purchase_orders', COUNT(*) FROM stg_purchase_orders
UNION ALL SELECT 'stg_deliveries', COUNT(*) FROM stg_deliveries
UNION ALL SELECT 'stg_sales', COUNT(*) FROM stg_sales
UNION ALL SELECT 'stg_inventory', COUNT(*) FROM stg_inventory;

-- 2. Exact duplicate rows (extra copies) in purchase orders and deliveries
SELECT 'purchase_orders' AS tbl, COALESCE(SUM(copies - 1), 0) AS duplicate_rows
FROM (SELECT COUNT(*) AS copies FROM stg_purchase_orders
      GROUP BY po_id, line_no, order_date, vendor_id, vendor_name, item_id, quantity,
               unit_price, order_type, promised_date, buyer_id
      HAVING COUNT(*) > 1) d
UNION ALL
SELECT 'deliveries', COALESCE(SUM(copies - 1), 0)
FROM (SELECT COUNT(*) AS copies FROM stg_deliveries
      GROUP BY delivery_id, po_id, line_no, received_date, qty_received, qty_rejected
      HAVING COUNT(*) > 1) d;

-- 3. Date formats in order_date
SELECT CASE
         WHEN order_date IS NULL                                  THEN 'blank'
         WHEN order_date REGEXP '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'    THEN 'YYYY-MM-DD'
         WHEN order_date REGEXP '^[0-9]{2}/[0-9]{2}/[0-9]{4}$'    THEN 'DD/MM/YYYY'
         WHEN order_date REGEXP '^[0-9]{1,2}-[A-Za-z]{3}-[0-9]{2}$' THEN 'D-Mon-YY'
         ELSE 'unknown'
       END AS date_format,
       COUNT(*) AS n_rows
FROM stg_purchase_orders
GROUP BY date_format
ORDER BY n_rows DESC;

-- 4. Spellings of order_type
-- GROUP BY BINARY is needed: the default collation (utf8mb4_unicode_ci) ignores case and
-- trailing spaces, so a plain GROUP BY would merge 'Regular', 'REGULAR' and 'Regular ' into one.
SELECT CONCAT('[', order_type, ']') AS order_type_as_stored, COUNT(*) AS n_rows
FROM stg_purchase_orders
GROUP BY BINARY order_type
ORDER BY n_rows DESC;

-- 5. Field-level problems in purchase orders
SELECT SUM(vendor_id IS NULL)                       AS blank_vendor_id,
       SUM(vendor_id REGEXP '^V15[1-5]$')           AS on_duplicate_vendor_codes,
       SUM(unit_price LIKE '₹%')                    AS price_with_rupee_symbol,
       SUM(unit_price IS NULL)                      AS blank_price,
       SUM(CAST(quantity AS SIGNED) <= 0)           AS zero_or_negative_qty,
       SUM(promised_date IS NULL)                   AS blank_promised_date
FROM stg_purchase_orders;

-- 6. Deliveries: orphans, blank / impossible rejections
SELECT SUM(po.po_id IS NULL)                                           AS orphan_receipts,
       SUM(d.qty_rejected IS NULL)                                     AS blank_qty_rejected,
       SUM(CAST(d.qty_rejected AS SIGNED) > CAST(d.qty_received AS SIGNED)) AS rejected_gt_received
FROM stg_deliveries d
LEFT JOIN (SELECT DISTINCT po_id, line_no FROM stg_purchase_orders) po
       ON po.po_id = d.po_id AND po.line_no = d.line_no;

-- 7. Vendor master: suspected duplicate registrations (same city + category, same name ignoring case/spaces)
SELECT a.vendor_id AS original, b.vendor_id AS duplicate, a.vendor_name AS original_name,
       b.vendor_name AS duplicate_name, a.city
FROM stg_vendors a
JOIN stg_vendors b
  ON a.city = b.city AND a.category = b.category AND a.vendor_id < b.vendor_id
 AND LEFT(LOWER(REPLACE(REPLACE(a.vendor_name, '.', ''), ' ', '')), 12)
   = LEFT(LOWER(REPLACE(REPLACE(b.vendor_name, '.', ''), ' ', '')), 12);

-- 8. Negative stock and blank sales quantities
SELECT (SELECT SUM(CAST(qty_on_hand AS SIGNED) < 0) FROM stg_inventory) AS negative_stock_rows,
       (SELECT SUM(qty_sold IS NULL) FROM stg_sales)                    AS blank_qty_sold,
       (SELECT SUM(month REGEXP '^[A-Za-z]{3}-[0-9]{4}$') FROM stg_sales) AS month_as_mon_yyyy;
