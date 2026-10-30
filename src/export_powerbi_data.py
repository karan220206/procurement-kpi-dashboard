"""
Export the tables the Power BI dashboard reads into data/powerbi/*.csv.

The dashboard loads these CSVs (no database driver needed on the viewing PC). Re-run this script
after the pipeline changes, then press Refresh in Power BI Desktop.

Run from the project root:
    .venv/Scripts/python src/export_powerbi_data.py
"""
import pandas as pd
from sqlalchemy import text

from db import get_engine
from utils import REPORTS_DIR, ROOT

OUT = ROOT / "data" / "powerbi"

QUERIES = {
    # One row per PO line, with the delivery flags and like-for-like price differences used by the measures
    "fact_po_lines": """
        SELECT l.po_id, l.line_no, l.order_date, l.promised_date, l.order_type, l.buyer_id, l.vendor_id, l.item_id,
               l.quantity, l.unit_price, l.standard_price, l.line_value,
               l.qty_received, l.qty_rejected, l.qty_inspected, l.receipts_with_rejection, l.receipts_inspected,
               l.lead_time_days, l.delay_days, l.is_due, l.is_on_time, l.is_otif, l.is_monsoon_month, l.line_status,
               CASE WHEN l.is_due THEN l.quantity END                        AS qty_due,
               CASE WHEN l.is_due THEN LEAST(l.qty_received, l.quantity) END AS qty_filled_due,
               CASE WHEN p.order_type = 'Bulk' THEN -p.diff_vs_regular END   AS bulk_saving,
               CASE WHEN p.order_type = 'Urgent' THEN p.diff_vs_regular END  AS urgent_premium
        FROM v_po_lines l
        LEFT JOIN v_price_vs_regular p USING (po_id, line_no)
    """,
    "dim_vendor": """
        SELECT v.vendor_id, CONCAT(v.vendor_id, '  ', v.vendor_name) AS vendor_label, v.vendor_name,
               v.category AS vendor_category, v.city, v.state AS vendor_state, v.payment_terms,
               r.risk_rank, r.risk_score, r.risk_tier, r.red_flags, r.main_driver,
               r.performance_score, r.exposure_score, r.category_share_pct, r.otd_change_pp
        FROM vendors v
        LEFT JOIN vendor_risk_scores r USING (vendor_id)
    """,
    "dim_item": "SELECT item_id, item_name, category, unit_of_measure, standard_price FROM items",
    "inventory_items": """
        SELECT item_id, standard_price, opening_qty, prev_year_end_qty, closing_qty, sold_last_year,
               avg_monthly_sales_6m, months_of_cover, closing_value, excess_qty, excess_value
        FROM kpi_inventory_items
    """,
    "upcoming_risk": """
        SELECT po_id, line_no, vendor_id, category, order_type, order_date, promised_date, line_value,
               late_probability, risk_band
        FROM po_line_late_risk
    """,
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    engine = get_engine()
    for name, sql in QUERIES.items():
        df = pd.read_sql(text(sql), engine)
        df.to_csv(OUT / f"{name}.csv", index=False, date_format="%Y-%m-%d", encoding="utf-8")
        print(f"{name:<18}{len(df):>8,} rows")
    # Static result tables from the analysis notebooks
    # Number the scenario rows so the table reads top-down: re-sourced volume first, then all of 2025
    order = ["On-time delivery, re-sourced lines (%)", "Average lead time, re-sourced lines (days)",
             "On-time delivery, all 2025 lines (%)", "Average lead time, all 2025 lines (days)",
             "Late lines avoided (expected)", "Cost change from price differences (₹ crore)"]
    scenario = pd.read_csv(REPORTS_DIR / "risk" / "resourcing_scenario.csv").set_index("measure").loc[order].reset_index()
    scenario["measure"] = [f"{i}. {m}" for i, m in enumerate(scenario.measure, start=1)]
    scenario.to_csv(OUT / "scenario.csv", index=False)
    models = pd.read_csv(REPORTS_DIR / "risk" / "delay_model_results.csv").set_axis(["model", "roc_auc", "pr_auc", "late_caught_top20", "precision_top20", "base_late_rate"], axis=1)
    models.to_csv(OUT / "model_results.csv", index=False)
    print(f"{'scenario':<18}{6:>8,} rows (copied)\n{'model_results':<18}{len(models):>8,} rows (copied)")


if __name__ == "__main__":
    main()
