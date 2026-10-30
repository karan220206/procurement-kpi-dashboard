-- =====================================================================================
-- Procurement KPI project: database schema (MariaDB 10.4+ / MySQL 8 compatible)
--
-- Creates procurement_db with two layers:
--   stg_*  staging tables: raw CSVs loaded as text, exactly as received (Phase 2)
--   clean  typed tables with keys and constraints, filled by the cleaning step (Phase 3)
--
-- Re-runnable: drops and recreates the whole database.
--   C:\xampp\mysql\bin\mysql.exe -u root < sql/01_schema.sql
-- =====================================================================================
SET NAMES utf8mb4;

DROP DATABASE IF EXISTS procurement_db;
CREATE DATABASE procurement_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE procurement_db;

-- -------------------------------------------------------------------------------------
-- Staging layer: every column is text; src_row = line number in the source CSV
-- -------------------------------------------------------------------------------------
CREATE TABLE stg_vendors (
    src_row          INT PRIMARY KEY,
    vendor_id        VARCHAR(20),
    vendor_name      VARCHAR(150),
    category         VARCHAR(60),
    city             VARCHAR(60),
    state            VARCHAR(60),
    onboarding_date  VARCHAR(20),
    payment_terms    VARCHAR(20)
);

CREATE TABLE stg_items (
    src_row          INT PRIMARY KEY,
    item_id          VARCHAR(20),
    item_name        VARCHAR(150),
    category         VARCHAR(60),
    unit_of_measure  VARCHAR(20),
    standard_price   VARCHAR(30)
);

CREATE TABLE stg_purchase_orders (
    src_row          INT PRIMARY KEY,
    po_id            VARCHAR(20),
    line_no          VARCHAR(10),
    order_date       VARCHAR(20),
    vendor_id        VARCHAR(20),
    vendor_name      VARCHAR(150),
    item_id          VARCHAR(20),
    quantity         VARCHAR(20),
    unit_price       VARCHAR(30),
    order_type       VARCHAR(20),
    promised_date    VARCHAR(20),
    buyer_id         VARCHAR(10)
);

CREATE TABLE stg_deliveries (
    src_row          INT PRIMARY KEY,
    delivery_id      VARCHAR(20),
    po_id            VARCHAR(20),
    line_no          VARCHAR(10),
    received_date    VARCHAR(20),
    qty_received     VARCHAR(20),
    qty_rejected     VARCHAR(20)
);

CREATE TABLE stg_sales (
    src_row          INT PRIMARY KEY,
    item_id          VARCHAR(20),
    month            VARCHAR(20),
    qty_sold         VARCHAR(20)
);

CREATE TABLE stg_inventory (
    src_row          INT PRIMARY KEY,
    item_id          VARCHAR(20),
    snapshot_date    VARCHAR(20),
    qty_on_hand      VARCHAR(20)
);

-- -------------------------------------------------------------------------------------
-- Clean layer: typed columns, primary/foreign keys and business-rule CHECKs.
-- dq_flags lists any fixes applied to a row (e.g. 'price_fixed_x100,promised_imputed').
-- -------------------------------------------------------------------------------------
CREATE TABLE vendors (
    vendor_id        VARCHAR(10)  PRIMARY KEY,
    vendor_name      VARCHAR(150) NOT NULL,
    category         VARCHAR(40)  NOT NULL,
    city             VARCHAR(40)  NOT NULL,
    state            VARCHAR(40)  NOT NULL,
    onboarding_date  DATE         NOT NULL,
    payment_terms    VARCHAR(20)  NOT NULL
);

-- Duplicate vendor registrations: raw code -> surviving vendor code
CREATE TABLE vendor_id_map (
    raw_vendor_id    VARCHAR(10) PRIMARY KEY,
    vendor_id        VARCHAR(10) NOT NULL,
    FOREIGN KEY (vendor_id) REFERENCES vendors (vendor_id)
);

CREATE TABLE items (
    item_id          VARCHAR(10)   PRIMARY KEY,
    item_name        VARCHAR(150)  NOT NULL,
    category         VARCHAR(40)   NOT NULL,
    unit_of_measure  VARCHAR(10)   NOT NULL,
    standard_price   DECIMAL(12,2) NOT NULL CHECK (standard_price > 0)
);

CREATE TABLE purchase_orders (
    po_id            VARCHAR(10)   NOT NULL,
    line_no          SMALLINT      NOT NULL,
    order_date       DATE          NOT NULL,
    vendor_id        VARCHAR(10)   NULL,          -- NULL only where the vendor could not be recovered
    item_id          VARCHAR(10)   NOT NULL,
    quantity         INT           NOT NULL CHECK (quantity > 0),
    unit_price       DECIMAL(12,2) NOT NULL CHECK (unit_price > 0),
    line_value       DECIMAL(16,2) AS (quantity * unit_price) PERSISTENT,
    order_type       VARCHAR(10)   NOT NULL CHECK (order_type IN ('Regular', 'Bulk', 'Urgent')),
    promised_date    DATE          NOT NULL,
    buyer_id         VARCHAR(5)    NOT NULL,
    dq_flags         VARCHAR(200)  NULL,
    PRIMARY KEY (po_id, line_no),
    FOREIGN KEY (vendor_id) REFERENCES vendors (vendor_id),
    FOREIGN KEY (item_id)   REFERENCES items (item_id),
    CHECK (promised_date >= order_date),
    INDEX idx_po_order_date (order_date),
    INDEX idx_po_vendor (vendor_id),
    INDEX idx_po_item (item_id)
);

CREATE TABLE deliveries (
    delivery_id      VARCHAR(10)  PRIMARY KEY,
    po_id            VARCHAR(10)  NOT NULL,
    line_no          SMALLINT     NOT NULL,
    received_date    DATE         NOT NULL,
    qty_received     INT          NOT NULL CHECK (qty_received > 0),
    qty_rejected     INT          NULL,           -- NULL = recorded value was invalid
    dq_flags         VARCHAR(200) NULL,
    FOREIGN KEY (po_id, line_no) REFERENCES purchase_orders (po_id, line_no),
    CHECK (qty_rejected IS NULL OR qty_rejected BETWEEN 0 AND qty_received),
    INDEX idx_dl_received (received_date)
);

CREATE TABLE sales (
    item_id          VARCHAR(10)  NOT NULL,
    month            DATE         NOT NULL,       -- first day of the month
    qty_sold         INT          NOT NULL CHECK (qty_sold >= 0),
    dq_flags         VARCHAR(200) NULL,
    PRIMARY KEY (item_id, month),
    FOREIGN KEY (item_id) REFERENCES items (item_id)
);

CREATE TABLE inventory (
    item_id          VARCHAR(10)  NOT NULL,
    snapshot_date    DATE         NOT NULL,
    qty_on_hand      INT          NOT NULL CHECK (qty_on_hand >= 0),
    dq_flags         VARCHAR(200) NULL,
    PRIMARY KEY (item_id, snapshot_date),
    FOREIGN KEY (item_id) REFERENCES items (item_id)
);

-- Rows removed during cleaning, with the reason (kept for audit, never silently deleted)
CREATE TABLE rejected_rows (
    source_table     VARCHAR(30)  NOT NULL,
    src_row          INT          NOT NULL,
    reason           VARCHAR(200) NOT NULL,
    PRIMARY KEY (source_table, src_row)
);
