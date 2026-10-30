-- =====================================================================================
-- Phase 3, step 1: standardise the staging data in SQL.
--
-- Creates std_* views that convert the raw text into proper types and spellings:
--   mixed date formats -> DATE, '₹1,234.50' -> DECIMAL, 'regular ' -> 'Regular',
--   'MH' / 'maharashtra ' -> 'Maharashtra', 'Mar-2024' -> 2024-03-01, ...
-- Rules that need context (duplicates, imputation, recovering IDs, outliers) are applied
-- afterwards in Python (src/clean_data.py), which reads these views.
--
--   C:\xampp\mysql\bin\mysql.exe -u root --default-character-set=utf8mb4 procurement_db < sql/03_standardize.sql
-- =====================================================================================
SET NAMES utf8mb4;
USE procurement_db;

DROP FUNCTION IF EXISTS parse_mixed_date;
DROP FUNCTION IF EXISTS parse_money;

DELIMITER //

-- '2024-03-05' / '05/03/2024' (day first) / '5-Mar-24' -> DATE; anything else -> NULL
CREATE FUNCTION parse_mixed_date(s VARCHAR(20)) RETURNS DATE DETERMINISTIC
BEGIN
    SET s = TRIM(s);
    RETURN CASE
        WHEN s REGEXP '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'       THEN STR_TO_DATE(s, '%Y-%m-%d')
        WHEN s REGEXP '^[0-9]{2}/[0-9]{2}/[0-9]{4}$'       THEN STR_TO_DATE(s, '%d/%m/%Y')
        WHEN s REGEXP '^[0-9]{1,2}-[A-Za-z]{3}-[0-9]{2}$'  THEN STR_TO_DATE(s, '%e-%b-%y')
        ELSE NULL
    END;
END //

-- '₹1,937.23' / '1937.23' / '' -> 1937.23 / 1937.23 / NULL
CREATE FUNCTION parse_money(s VARCHAR(30)) RETURNS DECIMAL(14,2) DETERMINISTIC
    RETURN CAST(NULLIF(TRIM(REPLACE(REPLACE(s, '₹', ''), ',', '')), '') AS DECIMAL(14,2)) //

DELIMITER ;

-- -------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW std_vendors AS
SELECT src_row,
       TRIM(vendor_id)                                   AS vendor_id,
       TRIM(REGEXP_REPLACE(vendor_name, ' +', ' '))      AS vendor_name,
       TRIM(category)                                    AS category,
       TRIM(city)                                        AS city,
       CASE LOWER(TRIM(state))
           WHEN 'mh' THEN 'Maharashtra'    WHEN 'maharashtra'    THEN 'Maharashtra'
           WHEN 'gj' THEN 'Gujarat'        WHEN 'gujarat'        THEN 'Gujarat'
           WHEN 'tn' THEN 'Tamil Nadu'     WHEN 'tamil nadu'     THEN 'Tamil Nadu'
           WHEN 'ka' THEN 'Karnataka'      WHEN 'karnataka'      THEN 'Karnataka'
           WHEN 'ts' THEN 'Telangana'      WHEN 'telangana'      THEN 'Telangana'
           WHEN 'wb' THEN 'West Bengal'    WHEN 'west bengal'    THEN 'West Bengal'
           WHEN 'dl' THEN 'Delhi'          WHEN 'delhi'          THEN 'Delhi'
           WHEN 'up' THEN 'Uttar Pradesh'  WHEN 'uttar pradesh'  THEN 'Uttar Pradesh'
           WHEN 'hr' THEN 'Haryana'        WHEN 'haryana'        THEN 'Haryana'
           WHEN 'pb' THEN 'Punjab'         WHEN 'punjab'         THEN 'Punjab'
           WHEN 'rj' THEN 'Rajasthan'      WHEN 'rajasthan'      THEN 'Rajasthan'
           WHEN 'kl' THEN 'Kerala'         WHEN 'kerala'         THEN 'Kerala'
           WHEN 'as' THEN 'Assam'          WHEN 'assam'          THEN 'Assam'
           WHEN 'mp' THEN 'Madhya Pradesh' WHEN 'madhya pradesh' THEN 'Madhya Pradesh'
           ELSE TRIM(state)
       END                                               AS state,
       parse_mixed_date(onboarding_date)                 AS onboarding_date,
       NULLIF(TRIM(payment_terms), '')                   AS payment_terms
FROM stg_vendors;

-- -------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW std_items AS
SELECT src_row,
       TRIM(item_id)                                     AS item_id,
       TRIM(item_name)                                   AS item_name,
       CASE LOWER(TRIM(category))
           WHEN 'raw materials'            THEN 'Raw Materials'
           WHEN 'packaging'                THEN 'Packaging'
           WHEN 'electrical & electronics' THEN 'Electrical & Electronics'
           WHEN 'mro'                      THEN 'MRO'
           WHEN 'it hardware'              THEN 'IT Hardware'
           WHEN 'chemicals'                THEN 'Chemicals'
           WHEN 'office supplies'          THEN 'Office Supplies'
           ELSE TRIM(category)
       END                                               AS category,
       NULLIF(TRIM(unit_of_measure), '')                 AS unit_of_measure,
       parse_money(standard_price)                       AS standard_price
FROM stg_items;

-- -------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW std_purchase_orders AS
SELECT src_row,
       TRIM(po_id)                                       AS po_id,
       CAST(line_no AS UNSIGNED)                         AS line_no,
       parse_mixed_date(order_date)                      AS order_date,
       NULLIF(TRIM(vendor_id), '')                       AS vendor_id,
       TRIM(REGEXP_REPLACE(vendor_name, ' +', ' '))      AS vendor_name,
       TRIM(item_id)                                     AS item_id,
       CAST(quantity AS SIGNED)                          AS quantity,
       parse_money(unit_price)                           AS unit_price,
       CONCAT(UPPER(LEFT(TRIM(order_type), 1)), LOWER(SUBSTRING(TRIM(order_type), 2))) AS order_type,
       parse_mixed_date(promised_date)                   AS promised_date,
       TRIM(buyer_id)                                    AS buyer_id
FROM stg_purchase_orders;

-- -------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW std_deliveries AS
SELECT src_row,
       TRIM(delivery_id)                                 AS delivery_id,
       TRIM(po_id)                                       AS po_id,
       CAST(line_no AS UNSIGNED)                         AS line_no,
       parse_mixed_date(received_date)                   AS received_date,
       CAST(qty_received AS SIGNED)                      AS qty_received,
       CAST(qty_rejected AS SIGNED)                      AS qty_rejected   -- NULL stays NULL
FROM stg_deliveries;

-- -------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW std_sales AS
SELECT src_row,
       TRIM(item_id)                                     AS item_id,
       CASE
           WHEN month REGEXP '^[A-Za-z]{3}-[0-9]{4}$' THEN STR_TO_DATE(CONCAT('01-', month), '%d-%b-%Y')
           WHEN month REGEXP '^[0-9]{4}-[0-9]{2}$'    THEN STR_TO_DATE(CONCAT(month, '-01'), '%Y-%m-%d')
       END                                               AS month,
       CAST(qty_sold AS SIGNED)                          AS qty_sold
FROM stg_sales;

-- -------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW std_inventory AS
SELECT src_row,
       TRIM(item_id)                                     AS item_id,
       parse_mixed_date(snapshot_date)                   AS snapshot_date,
       CAST(qty_on_hand AS SIGNED)                       AS qty_on_hand
FROM stg_inventory;

-- -------------------------------------------------------------------------------------
-- Quick check: every value should now parse (all counts expected 0 except the
-- genuinely blank fields that Python imputes)
-- -------------------------------------------------------------------------------------
SELECT
    (SELECT SUM(order_date IS NULL)    FROM std_purchase_orders) AS po_order_date_null,
    (SELECT SUM(promised_date IS NULL) FROM std_purchase_orders) AS po_promised_null,
    (SELECT SUM(unit_price IS NULL)    FROM std_purchase_orders) AS po_price_null,
    (SELECT COUNT(DISTINCT BINARY order_type) FROM std_purchase_orders) AS po_order_types,
    (SELECT SUM(received_date IS NULL) FROM std_deliveries)      AS dl_date_null,
    (SELECT SUM(month IS NULL)         FROM std_sales)           AS sales_month_null,
    (SELECT COUNT(DISTINCT state)      FROM std_vendors)         AS vendor_states,
    (SELECT SUM(onboarding_date IS NULL) FROM std_vendors)       AS vendor_onboard_null,
    (SELECT COUNT(DISTINCT BINARY category) FROM std_items)      AS item_categories,
    (SELECT SUM(standard_price IS NULL) FROM std_items)          AS item_price_null;
