"""Export the Market Research BQ tables to a single multi-sheet .xlsx for review.
Pulls the latest run per table. List/array columns are joined with '; '.
"""
from __future__ import annotations
import os, sys, datetime
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared"))
import config as C
import bq as BQ
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

DATASET = f"{C.BQ_PROJECT}.{C.BQ_DATASET}"
SHEETS = [
    ("Social_Trends",            "social_trends",      "run_date"),
    ("Blog_Publications",        "blog_publications",  "run_date"),
    ("Job_Market_Demand",        "job_market_demand",  "run_date"),
    ("Competitor_Intelligence",  "competitor_intel",   "run_date"),
    ("Executive_Summary",        "executive_summary",  "rank"),
]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output",
                   f"Market_Research_Output_{datetime.date.today().isoformat()}.xlsx")


def cellval(v):
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return "; ".join(str(x) for x in v)
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.isoformat()
    if isinstance(v, (int, float, str)):
        return v
    return str(v)


def main():
    cl = BQ.client()
    wb = Workbook()
    wb.remove(wb.active)
    hdr_fill = PatternFill("solid", fgColor="1F4E78")
    hdr_font = Font(bold=True, color="FFFFFF")
    summary = []

    for sheet_name, table, order in SHEETS:
        fqtn = f"{DATASET}.{table}"
        try:
            # latest run only (by run_date) where applicable
            latest = ""
            if order == "run_date":
                latest = (f"WHERE run_date = (SELECT MAX(run_date) FROM `{fqtn}`)")
            rows = [dict(r) for r in cl.query(
                f"SELECT * FROM `{fqtn}` {latest} ORDER BY {order}").result()]
        except Exception as e:
            print(f"[{table}] ERR {str(e)[:80]}")
            rows = []
        ws = wb.create_sheet(sheet_name[:31])
        if not rows:
            ws["A1"] = f"(no rows in {table})"
            summary.append((sheet_name, 0))
            continue
        cols = list(rows[0].keys())
        ws.append(cols)
        for j, c in enumerate(cols, 1):
            cell = ws.cell(row=1, column=j)
            cell.fill = hdr_fill; cell.font = hdr_font
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        for r in rows:
            ws.append([cellval(r.get(c)) for c in cols])
        # widths + wrap
        for j, c in enumerate(cols, 1):
            width = min(max(len(c) + 2, *(len(str(cellval(r.get(c)))) for r in rows)) , 60)
            ws.column_dimensions[get_column_letter(j)].width = max(12, width)
        ws.freeze_panes = "A2"
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        summary.append((sheet_name, len(rows)))
        print(f"[{table}] {len(rows)} rows -> sheet '{sheet_name}'")

    # cover sheet
    cover = wb.create_sheet("README", 0)
    cover["A1"] = "CK's AI/ML Market Research India — Agent Output"
    cover["A1"].font = Font(bold=True, size=14)
    cover["A3"] = f"Generated: {datetime.date.today().isoformat()} (review export)"
    cover["A4"] = f"Source: BigQuery {DATASET}"
    cover["A6"] = "Tabs:"
    for i, (name, n) in enumerate(summary, start=7):
        cover[f"A{i}"] = f"  • {name}: {n} rows"
    cover.column_dimensions["A"].width = 60

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    wb.save(OUT)
    print(f"\nSaved -> {OUT}")


if __name__ == "__main__":
    main()
