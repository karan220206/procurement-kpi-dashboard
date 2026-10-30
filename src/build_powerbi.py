"""
Generate the Power BI dashboard as a Power BI Project (.pbip): semantic model in TMDL + report layout.

Output: dashboard/Procurement KPI Dashboard.pbip (+ .SemanticModel and .Report folders).
Open the .pbip in Power BI Desktop and press Refresh to load data/powerbi/*.csv.

Run from the project root (after src/export_powerbi_data.py):
    .venv/Scripts/python src/build_powerbi.py
"""
import json
import shutil
import uuid

from utils import ROOT

NAME = "Procurement KPI Dashboard"
OUT = ROOT / "dashboard"
DATA = ROOT / "data" / "powerbi"


def guid(*parts):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "/".join(map(str, parts))))


# ======================================================================================
# Semantic model
# ======================================================================================
# (column, dataType, summarizeBy, formatString)
TABLES = {
    "fact_po_lines": [
        ("po_id", "string", "none", None), ("line_no", "int64", "none", None),
        ("order_date", "dateTime", "none", "dd-mmm-yyyy"), ("promised_date", "dateTime", "none", "dd-mmm-yyyy"),
        ("order_type", "string", "none", None), ("buyer_id", "string", "none", None),
        ("vendor_id", "string", "none", None), ("item_id", "string", "none", None),
        ("quantity", "int64", "sum", "#,0"), ("unit_price", "double", "none", "#,0.00"),
        ("standard_price", "double", "none", "#,0.00"), ("line_value", "double", "sum", "#,0"),
        ("qty_received", "double", "sum", "#,0"), ("qty_rejected", "double", "sum", "#,0"),
        ("qty_inspected", "double", "sum", "#,0"), ("receipts_with_rejection", "double", "sum", "#,0"),
        ("receipts_inspected", "double", "sum", "#,0"), ("lead_time_days", "double", "none", "0"),
        ("delay_days", "double", "none", "0"), ("is_due", "int64", "none", None),
        ("is_on_time", "int64", "none", None), ("is_otif", "int64", "none", None),
        ("is_monsoon_month", "int64", "none", None), ("line_status", "string", "none", None),
        ("qty_due", "double", "sum", "#,0"), ("qty_filled_due", "double", "sum", "#,0"),
        ("bulk_saving", "double", "sum", "#,0"), ("urgent_premium", "double", "sum", "#,0"),
    ],
    "dim_vendor": [
        ("vendor_id", "string", "none", None), ("vendor_label", "string", "none", None),
        ("vendor_name", "string", "none", None), ("vendor_category", "string", "none", None),
        ("city", "string", "none", None), ("vendor_state", "string", "none", None),
        ("payment_terms", "string", "none", None), ("risk_rank", "double", "none", "0"),
        ("risk_score", "double", "none", "0.0"), ("risk_tier", "string", "none", None),
        ("red_flags", "string", "none", None), ("main_driver", "string", "none", None),
        ("performance_score", "double", "none", "0.0"), ("exposure_score", "double", "none", "0.0"),
        ("category_share_pct", "double", "none", "0.0"), ("otd_change_pp", "double", "none", "+0.0;-0.0;0.0"),
    ],
    "dim_item": [
        ("item_id", "string", "none", None), ("item_name", "string", "none", None),
        ("category", "string", "none", None), ("unit_of_measure", "string", "none", None),
        ("standard_price", "double", "none", "#,0.00"),
    ],
    "inventory_items": [
        ("item_id", "string", "none", None), ("standard_price", "double", "none", "#,0.00"),
        ("opening_qty", "double", "sum", "#,0"), ("prev_year_end_qty", "double", "sum", "#,0"),
        ("closing_qty", "double", "sum", "#,0"), ("sold_last_year", "double", "sum", "#,0"),
        ("avg_monthly_sales_6m", "double", "none", "#,0.0"), ("months_of_cover", "double", "none", "0.0"),
        ("closing_value", "double", "sum", "#,0"), ("excess_qty", "double", "sum", "#,0"),
        ("excess_value", "double", "sum", "#,0"),
    ],
    "upcoming_risk": [
        ("po_id", "string", "none", None), ("line_no", "int64", "none", None),
        ("vendor_id", "string", "none", None), ("category", "string", "none", None),
        ("order_type", "string", "none", None), ("order_date", "dateTime", "none", "dd-mmm-yyyy"),
        ("promised_date", "dateTime", "none", "dd-mmm-yyyy"), ("line_value", "double", "sum", "#,0"),
        ("late_probability", "double", "none", "0%"), ("risk_band", "string", "none", None),
    ],
    "scenario": [
        ("measure", "string", "none", None), ("now", "double", "none", "#,0.0"),
        ("after_resourcing", "double", "none", "#,0.0"), ("change", "double", "none", "+#,0.0;-#,0.0;0.0"),
    ],
    "model_results": [
        ("model", "string", "none", None), ("roc_auc", "double", "none", "0.000"),
        ("pr_auc", "double", "none", "0.000"), ("late_caught_top20", "double", "none", "0.0%"),
        ("precision_top20", "double", "none", "0.0%"), ("base_late_rate", "double", "none", "0.0%"),
    ],
}

M_TYPES = {"string": "type text", "int64": "Int64.Type", "double": "type number", "dateTime": "type date"}

# (table, name, DAX, formatString, displayFolder)
MEASURES = [
    ("fact_po_lines", "Spend (₹ cr)", "DIVIDE(SUM(fact_po_lines[line_value]), 10000000)", "#,0.0", "Spend"),
    ("fact_po_lines", "PO Lines", "COUNTROWS(fact_po_lines)", "#,0", "Spend"),
    ("fact_po_lines", "Lines Due", "CALCULATE(COUNTROWS(fact_po_lines), fact_po_lines[is_due] = 1)", "#,0", "Delivery"),
    ("fact_po_lines", "OTD %",
     "DIVIDE(CALCULATE(COUNTROWS(fact_po_lines), fact_po_lines[is_due] = 1, fact_po_lines[is_on_time] = 1), [Lines Due])",
     "0.0%", "Delivery"),
    ("fact_po_lines", "OTIF %",
     "DIVIDE(CALCULATE(COUNTROWS(fact_po_lines), fact_po_lines[is_due] = 1, fact_po_lines[is_otif] = 1), [Lines Due])",
     "0.0%", "Delivery"),
    ("fact_po_lines", "Fill Rate %", "DIVIDE(SUM(fact_po_lines[qty_filled_due]), SUM(fact_po_lines[qty_due]))",
     "0.0%", "Delivery"),
    ("fact_po_lines", "Avg Delay (days)",
     "CALCULATE(AVERAGE(fact_po_lines[delay_days]), fact_po_lines[delay_days] > 0)", "0.0", "Delivery"),
    ("fact_po_lines", "Avg Lead Time (days)", "AVERAGE(fact_po_lines[lead_time_days])", "0.0", "Delivery"),
    ("fact_po_lines", "Overdue Open Lines",
     'CALCULATE(COUNTROWS(fact_po_lines), fact_po_lines[is_due] = 1, fact_po_lines[line_status] = "Open")',
     "#,0", "Delivery"),
    ("fact_po_lines", "Rejection Rate %",
     "DIVIDE(SUM(fact_po_lines[qty_rejected]), SUM(fact_po_lines[qty_inspected]))", "0.00%", "Quality"),
    ("fact_po_lines", "Receipts with Rejections %",
     "DIVIDE(SUM(fact_po_lines[receipts_with_rejection]), SUM(fact_po_lines[receipts_inspected]))", "0.0%", "Quality"),
    ("fact_po_lines", "Urgent Orders %",
     'DIVIDE(CALCULATE(COUNTROWS(fact_po_lines), fact_po_lines[order_type] = "Urgent"), [PO Lines])', "0.0%", "Buying"),
    ("fact_po_lines", "Bulk Orders %",
     'DIVIDE(CALCULATE(COUNTROWS(fact_po_lines), fact_po_lines[order_type] = "Bulk"), [PO Lines])', "0.0%", "Buying"),
    ("fact_po_lines", "Bulk Savings (₹ cr)", "DIVIDE(SUM(fact_po_lines[bulk_saving]), 10000000)", "#,0.0", "Buying"),
    ("fact_po_lines", "Urgent Premium (₹ cr)", "DIVIDE(SUM(fact_po_lines[urgent_premium]), 10000000)", "#,0.00", "Buying"),
    ("fact_po_lines", "PPV vs Standard %",
     "DIVIDE(SUMX(fact_po_lines, (fact_po_lines[unit_price] - fact_po_lines[standard_price]) * fact_po_lines[quantity]), "
     "SUMX(fact_po_lines, fact_po_lines[standard_price] * fact_po_lines[quantity]))", "+0.0%;-0.0%;0.0%", "Buying"),
    ("fact_po_lines", "Top Vendor Share %",
     "DIVIDE(MAXX(VALUES(fact_po_lines[vendor_id]), CALCULATE(SUM(fact_po_lines[line_value]))), "
     "SUM(fact_po_lines[line_value]))", "0.0%", "Dependency"),
    ("fact_po_lines", "Top 5 Vendor Share %",
     "DIVIDE(SUMX(TOPN(5, VALUES(fact_po_lines[vendor_id]), CALCULATE(SUM(fact_po_lines[line_value]))), "
     "CALCULATE(SUM(fact_po_lines[line_value]))), SUM(fact_po_lines[line_value]))", "0.0%", "Dependency"),
    ("fact_po_lines", "Vendor HHI",
     "VAR total = SUM(fact_po_lines[line_value]) RETURN "
     "SUMX(VALUES(fact_po_lines[vendor_id]), DIVIDE(CALCULATE(SUM(fact_po_lines[line_value])), total) ^ 2) * 10000",
     "#,0", "Dependency"),
    ("fact_po_lines", "Single-Source Items %",
     "VAR bought = VALUES(fact_po_lines[item_id]) RETURN "
     "DIVIDE(COUNTROWS(FILTER(bought, CALCULATE(DISTINCTCOUNT(fact_po_lines[vendor_id])) = 1)), COUNTROWS(bought))",
     "0.0%", "Dependency"),
    ("inventory_items", "Stock Value (₹ cr)", "DIVIDE(SUM(inventory_items[closing_value]), 10000000)", "#,0.0", None),
    ("inventory_items", "Excess Inventory (₹ cr)", "DIVIDE(SUM(inventory_items[excess_value]), 10000000)", "#,0.0", None),
    ("inventory_items", "Excess Share %",
     "DIVIDE(SUM(inventory_items[excess_value]), SUM(inventory_items[closing_value]))", "0.0%", None),
    ("inventory_items", "Items Over 6m Cover",
     "CALCULATE(COUNTROWS(inventory_items), inventory_items[months_of_cover] > 6)", "#,0", None),
    ("inventory_items", "Inventory Turnover",
     "DIVIDE(SUMX(inventory_items, inventory_items[sold_last_year] * inventory_items[standard_price]), "
     "SUMX(inventory_items, (inventory_items[prev_year_end_qty] + inventory_items[closing_qty]) / 2 "
     "* inventory_items[standard_price]))", "0.00", None),
    ("inventory_items", "Days on Hand", "DIVIDE(365, [Inventory Turnover])", "0", None),
    ("dim_vendor", "High-Risk Vendors", 'CALCULATE(COUNTROWS(dim_vendor), dim_vendor[risk_tier] = "High")', "#,0", None),
    ("dim_vendor", "Red-Flag Vendors", 'CALCULATE(COUNTROWS(dim_vendor), dim_vendor[red_flags] <> "")', "#,0", None),
    ("dim_vendor", "High-Risk Spend Share %",
     "DIVIDE(CALCULATE([Spend (₹ cr)], dim_vendor[risk_tier] = \"High\"), [Spend (₹ cr)])", "0.0%", None),
    ("dim_vendor", "Avg Risk Score", "AVERAGE(dim_vendor[risk_score])", "0.0", None),
    ("dim_vendor", "Performance Risk", "AVERAGE(dim_vendor[performance_score])", "0.0", None),
    ("dim_vendor", "Exposure", "AVERAGE(dim_vendor[exposure_score])", "0.0", None),
    ("upcoming_risk", "Upcoming High-Risk Lines",
     'CALCULATE(COUNTROWS(upcoming_risk), upcoming_risk[risk_band] = "High")', "#,0", None),
    ("upcoming_risk", "Upcoming Lines", "COUNTROWS(upcoming_risk)", "#,0", None),
]

RELATIONSHIPS = [
    ("fact_po_lines", "vendor_id", "dim_vendor", "vendor_id"),
    ("fact_po_lines", "item_id", "dim_item", "item_id"),
    ("fact_po_lines", "order_date", "dim_date", "Date"),
    ("inventory_items", "item_id", "dim_item", "item_id"),
    ("upcoming_risk", "vendor_id", "dim_vendor", "vendor_id"),
]


def q(name):
    """Quote a TMDL object name when needed."""
    return name if name.replace("_", "").isalnum() else "'" + name.replace("'", "''") + "'"


def table_tmdl(table, columns):
    lines = [f"table {table}", f"\tlineageTag: {guid('table', table)}", ""]
    for name, expr, fmt, folder in [(m[1], m[2], m[3], m[4]) for m in MEASURES if m[0] == table]:
        lines += [f"\tmeasure {q(name)} = {expr}", f"\t\tformatString: {fmt}"]
        if folder:
            lines.append(f"\t\tdisplayFolder: {folder}")
        lines += [f"\t\tlineageTag: {guid('measure', table, name)}", ""]
    for name, dtype, summarize, fmt in columns:
        lines += [f"\tcolumn {q(name)}", f"\t\tdataType: {dtype}"]
        if fmt:
            lines.append(f"\t\tformatString: {fmt}")
        lines += [f"\t\tlineageTag: {guid('column', table, name)}", f"\t\tsummarizeBy: {summarize}",
                  f"\t\tsourceColumn: {name}", ""]
    types = ", ".join(f'{{"{n}", {M_TYPES[d]}}}' for n, d, _, _ in columns)
    m = [
        "let",
        f'    Source = Csv.Document(File.Contents(ProjectFolder & "\\data\\powerbi\\{table}.csv"), '
        '[Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
        f'    Typed = Table.TransformColumnTypes(Promoted, {{{types}}}, "en-US")',
        "in",
        "    Typed",
    ]
    lines += [f"\tpartition {table} = m", "\t\tmode: import", "\t\tsource ="]
    lines += [f"\t\t\t\t{x}" for x in m]
    return "\n".join(lines) + "\n"


DATE_TMDL = f"""table dim_date
	lineageTag: {guid('table', 'dim_date')}
	dataCategory: Time

	column Date
		dataType: dateTime
		isKey
		formatString: dd-mmm-yyyy
		lineageTag: {guid('column', 'dim_date', 'Date')}
		summarizeBy: none
		isNameInferred
		sourceColumn: [Date]

	column Year
		dataType: int64
		formatString: 0
		lineageTag: {guid('column', 'dim_date', 'Year')}
		summarizeBy: none
		isNameInferred
		sourceColumn: [Year]

	column 'Month No'
		dataType: int64
		formatString: 0
		lineageTag: {guid('column', 'dim_date', 'Month No')}
		summarizeBy: none
		isNameInferred
		sourceColumn: [Month No]

	column Month
		dataType: string
		lineageTag: {guid('column', 'dim_date', 'Month')}
		summarizeBy: none
		isNameInferred
		sourceColumn: [Month]
		sortByColumn: 'Month Start'

	column 'Month Start'
		dataType: dateTime
		formatString: mmm yyyy
		lineageTag: {guid('column', 'dim_date', 'Month Start')}
		summarizeBy: none
		isNameInferred
		sourceColumn: [Month Start]

	partition dim_date = calculated
		mode: import
		source = ADDCOLUMNS(CALENDAR(DATE(2023, 1, 1), DATE(2026, 3, 31)), "Year", YEAR([Date]), "Month No", MONTH([Date]), "Month", FORMAT([Date], "mmm yyyy"), "Month Start", DATE(YEAR([Date]), MONTH([Date]), 1))
"""


def write_model(root):
    d = root / f"{NAME}.SemanticModel"
    (d / "definition" / "tables").mkdir(parents=True)
    (d / "definition.pbism").write_text(json.dumps({"version": "4.0", "settings": {}}, indent=2), encoding="utf-8")
    (d / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": NAME},
        "config": {"version": "2.0", "logicalId": guid("model")}}, indent=2), encoding="utf-8")
    defn = d / "definition"
    (defn / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1567\n", encoding="utf-8")
    all_tables = list(TABLES) + ["dim_date"]
    model = ["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
             "\tsourceQueryCulture: en-US", "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull",
             "", "annotation __PBI_TimeIntelligenceEnabled = 0", ""]
    model += [f"ref table {t}" for t in all_tables]
    (defn / "model.tmdl").write_text("\n".join(model) + "\n", encoding="utf-8")
    (defn / "expressions.tmdl").write_text(
        f'expression ProjectFolder = "{ROOT}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]\n'
        f"\tlineageTag: {guid('expr', 'ProjectFolder')}\n\n\tannotation PBI_ResultType = Text\n", encoding="utf-8")
    for t, cols in TABLES.items():
        (defn / "tables" / f"{t}.tmdl").write_text(table_tmdl(t, cols), encoding="utf-8")
    (defn / "tables" / "dim_date.tmdl").write_text(DATE_TMDL, encoding="utf-8")
    rel = []
    for ft, fc, tt, tc in RELATIONSHIPS:
        rel += [f"relationship {guid('rel', ft, fc, tt)}", f"\tfromColumn: {ft}.{q(fc)}", f"\ttoColumn: {tt}.{q(tc)}", ""]
    (defn / "relationships.tmdl").write_text("\n".join(rel), encoding="utf-8")


# ======================================================================================
# Report
# ======================================================================================
BLUE, ORANGE, AQUA, GREY, INK, INK2 = "#2a78d6", "#eb6834", "#1baf7a", "#c3c2b7", "#0b0b0b", "#52514e"
THEME = {
    "name": "Procurement KPI",
    "dataColors": [BLUE, ORANGE, AQUA, "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
    "background": "#ffffff", "foreground": INK, "tableAccent": BLUE,
    "textClasses": {
        "callout": {"fontSize": 26, "fontFace": "Segoe UI Semibold", "color": INK},
        "title": {"fontSize": 12, "fontFace": "Segoe UI Semibold", "color": INK},
        "header": {"fontSize": 12, "fontFace": "Segoe UI Semibold", "color": INK},
        "label": {"fontSize": 10, "fontFace": "Segoe UI", "color": INK2},
    },
    "visualStyles": {
        "*": {"*": {
            "background": [{"show": True, "color": {"solid": {"color": "#ffffff"}}, "transparency": 0}],
            "border": [{"show": True, "color": {"solid": {"color": "#e4e3de"}}, "radius": 6}],
            "dropShadow": [{"show": False}],
            "padding": [{"top": 8, "bottom": 8, "left": 10, "right": 10}],
        }},
        "page": {"*": {"background": [{"color": {"solid": {"color": "#f4f3ef"}}, "transparency": 0}]}},
    },
}


LABELS = {
    "vendor_label": "Vendor", "risk_tier": "Risk tier", "risk_score": "Risk score", "main_driver": "Main driver",
    "red_flags": "Red flags", "po_id": "PO", "line_no": "Line", "promised_date": "Promised", "line_value": "Value (₹)",
    "late_probability": "Late probability", "risk_band": "Risk", "item_name": "Item", "category": "Category",
    "closing_qty": "Closing qty", "avg_monthly_sales_6m": "Avg monthly sales", "months_of_cover": "Months of cover",
    "measure": "Measure", "now": "Now", "after_resourcing": "After re-sourcing", "change": "Change", "model": "Model",
    "roc_auc": "ROC-AUC", "pr_auc": "PR-AUC", "late_caught_top20": "Late lines caught (riskiest 20%)",
    "precision_top20": "Precision (riskiest 20%)", "base_late_rate": "Base late rate", "vendor_state": "Vendor state",
    "order_type": "Order type", "Month Start": "Month",
}


def lit(v):
    """Literal for visual formatting objects."""
    if isinstance(v, bool):
        return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
    if isinstance(v, (int, float)):
        return {"expr": {"Literal": {"Value": f"{v}D"}}}
    return {"expr": {"Literal": {"Value": f"'{v}'"}}}


def color(c):
    return {"solid": {"color": lit(c)}}


class Visual:
    def __init__(self, vtype, x, y, w, h, title=None):
        self.vtype, self.pos, self.title = vtype, (x, y, w, h), title
        self.projections, self.select, self.order, self.objects = {}, [], [], {}
        self.aliases = {}

    def _src(self, table):
        if table not in self.aliases:
            self.aliases[table] = f"t{len(self.aliases)}"
        return {"SourceRef": {"Source": self.aliases[table]}}

    def add(self, role, table, field, kind="column", sort=None):
        key = "Measure" if kind == "measure" else "Column"
        ref = f"{table}.{field}"
        if ref not in [s["Name"] for s in self.select]:
            self.select.append({key: {"Expression": self._src(table), "Property": field}, "Name": ref})
        self.projections.setdefault(role, []).append({"queryRef": ref})
        if sort:
            self.order.append({"Direction": 2 if sort == "desc" else 1,
                               "Expression": {key: {"Expression": self._src(table), "Property": field}}})
        return self

    def config(self, i):
        sv = {"visualType": self.vtype, "projections": self.projections,
              "prototypeQuery": {"Version": 2,
                                 "From": [{"Name": a, "Entity": t, "Type": 0} for t, a in self.aliases.items()],
                                 "Select": self.select},
              "drillFilterOtherVisuals": True, "objects": self.objects}
        if self.order:
            sv["prototypeQuery"]["OrderBy"] = self.order
        labels = {s["Name"]: {"displayName": LABELS[s["Name"].split(".", 1)[1]]} for s in self.select
                  if s["Name"].split(".", 1)[1] in LABELS}
        if labels:
            sv["columnProperties"] = labels
        if self.title:
            sv["vcObjects"] = {"title": [{"properties": {"show": lit(True), "text": lit(self.title),
                                                         "fontColor": color(INK), "fontSize": lit(11)}}]}
        x, y, w, h = self.pos
        return {"name": guid("visual", i, self.vtype, self.title), "layouts": [{"id": 0, "position":
                {"x": x, "y": y, "z": i, "width": w, "height": h, "tabOrder": i}}], "singleVisual": sv}


def textbox(x, y, w, h, title, subtitle):
    runs = [{"textRuns": [{"value": title, "textStyle": {"fontWeight": "bold", "fontSize": "16pt", "color": INK}}]},
            {"textRuns": [{"value": subtitle, "textStyle": {"fontSize": "9pt", "color": INK2}}]}]
    v = Visual("textbox", x, y, w, h)
    v.objects = {"general": [{"properties": {"paragraphs": runs}}],
                 "background": [{"properties": {"show": lit(False)}}], "border": [{"properties": {"show": lit(False)}}]}
    return v


def card(x, y, w, h, measure, table="fact_po_lines", label=None):
    v = Visual("card", x, y, w, h).add("Values", table, measure, "measure")
    v.objects = {"labels": [{"properties": {"color": color(INK), "fontSize": lit(22)}}],
                 "categoryLabels": [{"properties": {"show": lit(True), "color": color(INK2), "fontSize": lit(10)}}]}
    return v


def slicer(x, y, w, h, table, column, title):
    v = Visual("slicer", x, y, w, h, title).add("Values", table, column)
    v.objects = {"data": [{"properties": {"mode": lit("Dropdown")}}],
                 "header": [{"properties": {"show": lit(False)}}]}
    return v


def bar(vtype, x, y, w, h, title, cat, measures, sort_measure=None, color_hex=BLUE):
    v = Visual(vtype, x, y, w, h, title).add("Category", *cat)
    for i, (t, m) in enumerate(measures):
        v.add("Y", t, m, "measure", sort="desc" if (sort_measure is None and i == 0) or m == sort_measure else None)
    if len(measures) == 1:
        v.objects["dataPoint"] = [{"properties": {"fill": color(color_hex)}}]
    v.objects["labels"] = [{"properties": {"show": lit(True), "color": color(INK2), "fontSize": lit(8)}}]
    return v


def line(x, y, w, h, title, measures, colors=(BLUE, ORANGE)):
    v = Visual("lineChart", x, y, w, h, title).add("Category", "dim_date", "Month Start")
    for t, m in measures:
        v.add("Y", t, m, "measure")
    v.objects["dataPoint"] = [{"properties": {"fill": color(c)}, "selector": {"metadata": f"{t}.{m}"}}
                              for (t, m), c in zip(measures, colors)]
    v.objects["legend"] = [{"properties": {"show": lit(len(measures) > 1), "position": lit("Top")}}]
    return v


def table_visual(x, y, w, h, title, fields, sort=None):
    v = Visual("tableEx", x, y, w, h, title)
    for t, f, kind, *direction in fields:
        v.add("Values", t, f, kind, sort=direction[0] if direction else ("desc" if f == sort else None))
    v.objects["grid"] = [{"properties": {"textSize": lit(9)}}]
    v.objects["total"] = [{"properties": {"totals": lit(False)}}]
    v.objects["columnHeaders"] = [{"properties": {"fontColor": color(INK), "backColor": color("#f4f3ef")}}]
    return v


def scatter(x, y, w, h, title, cat, xm, ym, size, series=None, series_colors=None):
    v = Visual("scatterChart", x, y, w, h, title).add("Category", *cat)
    v.add("X", *xm, "measure").add("Y", *ym, "measure").add("Size", *size, "measure")
    if series:
        v.add("Series", *series)
        v.objects["dataPoint"] = [
            {"properties": {"fill": color(c)}, "selector": {"data": [{"scopeId": {"Comparison": {
                "ComparisonKind": 0, "Left": {"Column": {"Expression": {"SourceRef": {"Entity": series[0]}},
                                                         "Property": series[1]}},
                "Right": {"Literal": {"Value": f"'{val}'"}}}}}]}}
            for val, c in series_colors.items()]
        v.objects["legend"] = [{"properties": {"show": lit(True), "position": lit("Top")}}]
    else:
        v.objects["dataPoint"] = [{"properties": {"fill": color(BLUE)}}]
    return v


F = "fact_po_lines"
W, H, M = 1280, 720, 16                 # page size and margin
COL = (W - 3 * M) // 2                  # half-width column
TOP = 168                               # y where charts start


def header(title, subtitle, slicers=True):
    vs = [textbox(M, 2, 620, 72, title, subtitle)]
    if slicers:
        specs = [("dim_date", "Year", "Year"), ("dim_item", "category", "Category"),
                 ("fact_po_lines", "order_type", "Order type"), ("dim_vendor", "vendor_state", "Vendor state")]
        for i, (t, c, label) in enumerate(specs):
            vs.append(slicer(652 + i * 154, 4, 146, 70, t, c, label))
    return vs


def card_row(specs):
    n = len(specs)
    w = (W - 2 * M - (n - 1) * 10) // n
    return [card(M + i * (w + 10), 78, w, 80, m, t) for i, (t, m) in enumerate(specs)]


PAGES = [
    ("Overview", lambda: header("Procurement KPI Dashboard", "Jan 2023 – Dec 2025 · ₹ crore · all filters apply to every visual on the page")
     + card_row([(F, "Spend (₹ cr)"), (F, "OTD %"), (F, "OTIF %"), (F, "Fill Rate %"),
                 (F, "Bulk Savings (₹ cr)"), ("inventory_items", "Excess Inventory (₹ cr)")])
     + [line(M, TOP, COL, 265, "Monthly spend (₹ crore, by order month)", [(F, "Spend (₹ cr)")]),
        line(2 * M + COL, TOP, COL, 265, "On-time delivery vs on-time in full", [(F, "OTD %"), (F, "OTIF %")]),
        bar("clusteredBarChart", M, TOP + 275, COL, 265, "Spend by category (₹ crore)",
            ("dim_item", "category"), [(F, "Spend (₹ cr)")]),
        bar("clusteredBarChart", 2 * M + COL, TOP + 275, COL, 265, "On-time delivery by category",
            ("dim_item", "category"), [(F, "OTD %")], color_hex=BLUE)]),
    ("Vendor Performance", lambda: header("Vendor Performance", "Delivery and quality by vendor · bubble size = spend")
     + card_row([(F, "OTD %"), (F, "OTIF %"), (F, "Avg Delay (days)"), (F, "Avg Lead Time (days)"),
                 (F, "Receipts with Rejections %"), (F, "Overdue Open Lines")])
     + [scatter(M, TOP, COL, 540, "On-time delivery vs quality (each bubble = a vendor)",
                ("dim_vendor", "vendor_label"), (F, "OTD %"), (F, "Receipts with Rejections %"), (F, "Spend (₹ cr)")),
        table_visual(2 * M + COL, TOP, COL, 540, "Vendor scorecard",
                     [("dim_vendor", "vendor_label", "column"), ("dim_vendor", "risk_tier", "column"),
                      (F, "Spend (₹ cr)", "measure"), (F, "OTD %", "measure"), (F, "OTIF %", "measure"),
                      (F, "Avg Delay (days)", "measure"), (F, "Receipts with Rejections %", "measure")],
                     sort="Spend (₹ cr)")]),
    ("Spend & Savings", lambda: header("Spend, Dependency & Savings", "Where the money goes and how buying behaviour affects price")
     + card_row([(F, "Top Vendor Share %"), (F, "Top 5 Vendor Share %"), (F, "Single-Source Items %"),
                 (F, "Bulk Savings (₹ cr)"), (F, "Urgent Premium (₹ cr)"), (F, "PPV vs Standard %")])
     + [bar("clusteredBarChart", M, TOP, COL, 540, "Spend by vendor, largest first (₹ crore)",
            ("dim_vendor", "vendor_label"), [(F, "Spend (₹ cr)")]),
        bar("clusteredColumnChart", 2 * M + COL, TOP, COL, 265, "Bulk-buy savings by category (₹ crore, vs regular price)",
            ("dim_item", "category"), [(F, "Bulk Savings (₹ cr)")], color_hex=AQUA),
        line(2 * M + COL, TOP + 275, COL, 265, "Share of PO lines raised as urgent vs bulk",
             [(F, "Urgent Orders %"), (F, "Bulk Orders %")], colors=(ORANGE, AQUA))]),
    ("Inventory", lambda: header("Inventory & Working Capital", "Closing stock at Dec 2025 · excess = stock above 6 months of cover", slicers=False)
     + [slicer(652, 4, 146, 70, "dim_item", "category", "Category")]
     + card_row([("inventory_items", "Stock Value (₹ cr)"), ("inventory_items", "Excess Inventory (₹ cr)"),
                 ("inventory_items", "Excess Share %"), ("inventory_items", "Items Over 6m Cover"),
                 ("inventory_items", "Inventory Turnover"), ("inventory_items", "Days on Hand")])
     + [bar("clusteredBarChart", M, TOP, COL, 540, "Stock value vs excess by category (₹ crore)",
            ("dim_item", "category"), [("inventory_items", "Stock Value (₹ cr)"), ("inventory_items", "Excess Inventory (₹ cr)")],
            sort_measure="Stock Value (₹ cr)"),
        table_visual(2 * M + COL, TOP, COL, 540, "Items with the most excess stock",
                     [("dim_item", "item_name", "column"), ("inventory_items", "closing_qty", "column"), ("inventory_items", "avg_monthly_sales_6m", "column"),
                      ("inventory_items", "months_of_cover", "column"), ("inventory_items", "Excess Inventory (₹ cr)", "measure")],
                     sort="Excess Inventory (₹ cr)")]),
    ("Vendor Risk", lambda: header("Vendor Risk", "Risk score 0–100 (performance 80%, exposure 20%) · High = score ≥ 50 or a red flag", slicers=False)
     + card_row([("dim_vendor", "High-Risk Vendors"), ("dim_vendor", "High-Risk Spend Share %"),
                 ("dim_vendor", "Red-Flag Vendors"), (F, "Vendor HHI"),
                 ("upcoming_risk", "Upcoming High-Risk Lines"), ("upcoming_risk", "Upcoming Lines")])
     + [scatter(M, TOP, COL, 540, "Risk matrix: performance risk vs exposure",
                ("dim_vendor", "vendor_label"), ("dim_vendor", "Performance Risk"), ("dim_vendor", "Exposure"),
                (F, "Spend (₹ cr)"), series=("dim_vendor", "risk_tier"),
                series_colors={"High": ORANGE, "Medium": BLUE, "Low": GREY, "Insufficient data": "#e4e3de"}),
        table_visual(2 * M + COL, TOP, COL, 265, "Highest-risk vendors",
                     [("dim_vendor", "vendor_label", "column"), ("dim_vendor", "risk_score", "column"),
                      ("dim_vendor", "risk_tier", "column"), ("dim_vendor", "main_driver", "column"),
                      ("dim_vendor", "red_flags", "column"), (F, "Spend (₹ cr)", "measure")], sort="risk_score"),
        table_visual(2 * M + COL, TOP + 275, COL, 265, "Early warning: open PO lines most likely to arrive late",
                     [("upcoming_risk", "po_id", "column"), ("upcoming_risk", "line_no", "column"),
                      ("dim_vendor", "vendor_label", "column"), ("upcoming_risk", "promised_date", "column"),
                      ("upcoming_risk", "line_value", "column"), ("upcoming_risk", "late_probability", "column"),
                      ("upcoming_risk", "risk_band", "column")], sort="late_probability")]),
    ("Scenario & Model", lambda: [textbox(M, 8, 900, 62, "Re-sourcing Scenario & Delay Model",
                                          "Static results from notebooks/04_risk_score.ipynb and 05_delay_model.ipynb")]
     + [table_visual(M, 90, W - 2 * M, 230,
                     "Scenario: move 2025 volume of the 10 largest High-risk vendors to qualified alternatives (+50% capacity cap)",
                     [("scenario", "measure", "column", "asc"), ("scenario", "now", "column"),
                      ("scenario", "after_resourcing", "column"), ("scenario", "change", "column")]),
        table_visual(M, 335, W - 2 * M, 170, "Late-delivery prediction on 2025 orders (trained on 2023–2024)",
                     [("model_results", "model", "column"), ("model_results", "roc_auc", "column"),
                      ("model_results", "pr_auc", "column"), ("model_results", "late_caught_top20", "column"),
                      ("model_results", "precision_top20", "column"), ("model_results", "base_late_rate", "column")]),
        textbox(M, 520, W - 2 * M, 90, "How to read this",
                "Best achievable ROC-AUC on this data is 0.690 (true probabilities); the logistic regression reaches 0.674, "
                "i.e. 92% of the achievable gain. The riskiest 10% of lines are late 51% of the time vs 9% for the safest 10%.")]),
]


def write_report(root):
    d = root / f"{NAME}.Report"
    res = d / "StaticResources" / "RegisteredResources"
    res.mkdir(parents=True)
    (res / "ProcurementTheme.json").write_text(json.dumps(THEME, indent=2), encoding="utf-8")
    (d / "definition.pbir").write_text(json.dumps(
        {"version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}}, indent=2),
        encoding="utf-8")
    (d / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": NAME},
        "config": {"version": "2.0", "logicalId": guid("report")}}, indent=2), encoding="utf-8")

    sections = []
    for p, (page_name, build) in enumerate(PAGES):
        containers = []
        for i, v in enumerate(build()):
            x, y, w, h = v.pos
            containers.append({"x": x, "y": y, "z": i, "width": w, "height": h,
                               "config": json.dumps(v.config(i), ensure_ascii=False), "filters": "[]"})
        sections.append({"name": guid("page", page_name)[:20].replace("-", ""), "displayName": page_name,
                         "displayOption": 1, "width": W, "height": H, "ordinal": p,
                         "config": "{}", "filters": "[]", "visualContainers": containers})
    report = {
        "config": json.dumps({"version": "5.59", "themeCollection": {
            "customTheme": {"name": "ProcurementTheme.json", "version": "5.59", "type": 1}},
            "activeSectionIndex": ACTIVE_PAGE, "settings": {"useStylableVisualContainerHeader": True}}),
        "layoutOptimization": 0,
        "resourcePackages": [{"resourcePackage": {"name": "RegisteredResources", "type": 1, "disabled": False,
                                                  "items": [{"name": "ProcurementTheme.json",
                                                             "path": "ProcurementTheme.json", "type": 201}]}}],
        "sections": sections,
    }
    (d / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


ACTIVE_PAGE = 0


def main():
    OUT.mkdir(exist_ok=True)
    for p in [OUT / f"{NAME}.SemanticModel", OUT / f"{NAME}.Report"]:
        if p.exists():
            shutil.rmtree(p)
    (OUT / f"{NAME}.pbip").write_text(json.dumps({
        "version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": False}}, indent=2), encoding="utf-8")
    write_model(OUT)
    write_report(OUT)
    print(f"Wrote {OUT / (NAME + '.pbip')}: {len(TABLES) + 1} tables, {len(MEASURES)} measures, "
          f"{len(RELATIONSHIPS)} relationships, {len(PAGES)} pages")


if __name__ == "__main__":
    import sys
    ACTIVE_PAGE = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    main()
