"""Build manager deliverables from output/processed.json + output/manifest.json:
  - ai_hiring_jobs_india.csv         (full normalized rows)
  - ai_hiring_trends_india.xlsx      (multi-sheet trends workbook)
  - REPORT.md                        (narrative for managers)
"""
import os, json, csv
from collections import Counter, defaultdict
import config as C

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "output")

rows = json.load(open(os.path.join(OUT, "processed.json"), encoding="utf-8"))
man = json.load(open(os.path.join(OUT, "manifest.json"), encoding="utf-8"))

COLS = ["source", "title", "role_bucket", "family", "company", "company_tier",
        "salary_norm", "location", "posted_date", "window", "query", "url"]

# ---- CSV ----
csv_path = os.path.join(OUT, "ai_hiring_jobs_india.csv")
with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["Source", "Job Role Title", "Normalized Role", "Role Family",
                "Company", "Company Tier", "Salary", "Location", "Posted Date",
                "In 2-Month Window", "Search Query", "Job URL"])
    for r in rows:
        w.writerow([r.get(c, "") for c in COLS])

# ---- Aggregations ----
by_role = Counter(r["role_bucket"] for r in rows if r.get("role_bucket"))
by_family = Counter(r["family"] for r in rows if r.get("family"))
by_tier = Counter(r["company_tier"] for r in rows if r.get("company_tier"))
by_source = Counter(r["source"] for r in rows)
by_company = Counter(r["company"] for r in rows if r.get("company"))
win = Counter(r["window"] for r in rows)
sal_have = sum(1 for r in rows if r.get("salary_norm"))

# per-source cost/raw/kept from manifest
src_stats = defaultdict(lambda: {"raw": 0, "kept": 0, "cost": 0.0, "runs": 0})
ran_sites = set()
for m in man["manifest"]:
    if "raw" in m:
        ran_sites.add(m["site"])
        s = src_stats[m["site"]]
        s["raw"] += m.get("raw", 0); s["kept"] += m.get("kept_ai", 0)
        s["cost"] += m.get("cost_usd", 0) or 0; s["runs"] += 1


def site_status(site):
    return "SCRAPED" if site in ran_sites else "NOT RUN (budget ceiling hit first)"

gov = man["governor"]

# ---- XLSX ----
try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    hdr_fill = PatternFill("solid", fgColor="1F4E78")
    hdr_font = Font(color="FFFFFF", bold=True)
    title_font = Font(bold=True, size=14)

    def style_header(ws, ncols, row=1):
        for c in range(1, ncols + 1):
            cell = ws.cell(row=row, column=c)
            cell.fill = hdr_fill; cell.font = hdr_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

    def autosize(ws, maxw=60):
        for col in ws.columns:
            length = max((len(str(c.value)) for c in col if c.value is not None), default=10)
            ws.column_dimensions[get_column_letter(col[0].column)].width = min(length + 2, maxw)

    # Summary
    ws = wb.active; ws.title = "Summary"
    ws["A1"] = "AI/ML Hiring Trends — India — Last 2 Months"; ws["A1"].font = title_font
    rowsout = [
        ["Window", f'{man["window"]["start"]} to {man["window"]["report_date"]}'],
        ["Total unique AI roles captured", len(rows)],
        ["In-window / unknown-date / out", f'{win.get("in",0)} / {win.get("unknown",0)} / {win.get("out",0)}'],
        ["Rows with salary data", f"{sal_have} ({round(100*sal_have/max(len(rows),1))}%)"],
        ["Sources scraped", len(by_source)],
        ["Spend this run (USD)", round(gov["session_spent"], 4)],
        ["Final monthly usage (USD / $5 cap)", f'{round(gov["final_usage"],4)} / 5.00'],
        [],
        ["TOP 10 AI ROLES BY OPENINGS", "count"],
    ]
    r = 3
    for pair in rowsout:
        for i, v in enumerate(pair):
            ws.cell(row=r, column=1 + i, value=v)
        r += 1
    for role, cnt in by_role.most_common(10):
        ws.cell(row=r, column=1, value=role); ws.cell(row=r, column=2, value=cnt); r += 1
    autosize(ws)

    def table_sheet(name, headers, data_rows):
        s = wb.create_sheet(name)
        s.append(headers); style_header(s, len(headers))
        for dr in data_rows:
            s.append(dr)
        s.freeze_panes = "A2"; autosize(s)
        return s

    table_sheet("By_Role", ["Normalized AI Role", "Openings"],
                [[k, v] for k, v in by_role.most_common()])
    table_sheet("By_Family", ["AI Role Family", "Openings"],
                [[k, v] for k, v in by_family.most_common()])
    table_sheet("By_Company_Tier", ["Company Tier", "Openings"],
                [[k, v] for k, v in by_tier.most_common()])
    table_sheet("Top_Companies", ["Company", "Company Tier", "Openings"],
                [[k, next((r["company_tier"] for r in rows if r["company"] == k), ""), v]
                 for k, v in by_company.most_common(40)])
    table_sheet("By_Source", ["Source", "Raw scraped", "Kept (AI)", "Runs", "Cost USD"],
                [[s, st["raw"], st["kept"], st["runs"], round(st["cost"], 4)]
                 for s, st in sorted(src_stats.items(), key=lambda x: -x[1]["kept"])])

    # Coverage
    cov = []
    for e in C.ROSTER:
        st = src_stats.get(e["site"], {"raw": 0, "kept": 0, "cost": 0})
        cov.append([e["site"], site_status(e["site"]), e["scope"], st["raw"], st["kept"], round(st["cost"], 4)])
    for b in C.BLOCKED_SITES:
        cov.append([b["site"], "BLOCKED", b["reason"], 0, 0, 0])
    table_sheet("Coverage", ["Requested Site", "Status", "Scope / Reason",
                             "Raw scraped", "Kept (AI)", "Cost USD"], cov)

    # All jobs
    aj = wb.create_sheet("All_Jobs")
    headers = ["Source", "Job Role Title", "Normalized Role", "Role Family", "Company",
               "Company Tier", "Salary", "Location", "Posted Date", "In Window", "Query", "URL"]
    aj.append(headers); style_header(aj, len(headers))
    for r_ in rows:
        aj.append([r_.get(c, "") for c in COLS])
    aj.freeze_panes = "A2"; autosize(aj, maxw=50)

    # Governance
    g = wb.create_sheet("Cost_Governance")
    g.append(["Guardrail", "Value"]); style_header(g, 2)
    for k, v in [
        ("Account plan", "FREE ($5/mo hard platform cap)"),
        ("Self-imposed soft ceiling (stop new runs)", f"${C.SESSION_SOFT_CEILING_USD}"),
        ("Self-imposed hard abort", f"${C.SESSION_HARD_ABORT_USD}"),
        ("Absolute-usage abort", f"${C.ACCOUNT_ABS_ABORT_USD}"),
        ("Baseline usage at run start", f'${round(gov["baseline"],4)}'),
        ("Spend this run", f'${round(gov["session_spent"],4)}'),
        ("Final monthly usage", f'${round(gov["final_usage"],4)} / $5.00'),
        ("Data retention (free plan)", "7 days -> exported locally immediately"),
    ]:
        g.append([k, v])
    autosize(g)

    xlsx_path = os.path.join(OUT, "ai_hiring_trends_india.xlsx")
    wb.save(xlsx_path)
    print("Wrote", xlsx_path)
except Exception as e:
    print("XLSX step error:", e)

# ---- REPORT.md ----
md = []
md.append("# AI/ML Hiring Trends — India — Last 2 Months\n")
md.append(f"**Window:** {man['window']['start']} → {man['window']['report_date']}  ")
md.append(f"**Generated:** {man['window']['report_date']}  ")
md.append(f"**Scope guardrail:** India · AI/ML roles only (healthcare, finance, generic SWE filtered out)\n")
md.append("> Reliability test of Apify job-scraper actors. Governed to a hard budget; "
          "all numbers are reproducible from `output/processed.json` + `output/manifest.json`.\n")

md.append("## 1. Headline\n")
md.append(f"- **{len(rows)} unique AI/ML openings** captured across **{len(by_source)} live sources** (India).")
md.append(f"- Date coverage: **{win.get('in',0)} in-window**, {win.get('unknown',0)} undated, {win.get('out',0)} older.")
md.append(f"- Salary disclosed on **{sal_have}/{len(rows)} ({round(100*sal_have/max(len(rows),1))}%)** roles (most India listings hide pay).")
md.append(f"- **Spend: ${round(gov['session_spent'],4)}** this run · final usage **${round(gov['final_usage'],4)} / $5.00 cap**.\n")
md.append("> ⚠️ **Coverage caveat:** Only **LinkedIn + Google Jobs** completed. Google Jobs' real cost "
          "was ~**$1.05/query** (vs ~$0.04 the 10-row probe implied — non-linear per-run fee), so it consumed "
          "the budget and the governor **correctly skipped Naukri, Glassdoor, Foundit, Indeed & HackerNews**. "
          "The $5 cap is now reached (resets ~2026-07-02). These figures = **LinkedIn + Google Jobs only.**\n")

md.append("## 2. Which AI roles have the most openings\n")
md.append("| Rank | Normalized AI Role | Openings |")
md.append("|---|---|---|")
for i, (role, cnt) in enumerate(by_role.most_common(15), 1):
    md.append(f"| {i} | {role} | {cnt} |")
md.append("")

md.append("## 3. By AI role family\n")
md.append("| AI Family | Openings |")
md.append("|---|---|")
for k, v in by_family.most_common():
    md.append(f"| {k} | {v} |")
md.append("")

md.append("## 4. By company tier\n")
md.append("| Company Tier | Openings |")
md.append("|---|---|")
for k, v in by_tier.most_common():
    md.append(f"| {k} | {v} |")
md.append("")

md.append("## 5. Top hiring companies (AI roles)\n")
md.append("| Company | Tier | Openings |")
md.append("|---|---|---|")
for k, v in by_company.most_common(20):
    tier = next((r["company_tier"] for r in rows if r["company"] == k), "")
    md.append(f"| {k} | {tier} | {v} |")
md.append("")

md.append("## 6. Source coverage & cost (governance)\n")
md.append("| Requested Site | Status | Raw | Kept (AI) | Cost USD |")
md.append("|---|---|---|---|---|")
for e in C.ROSTER:
    st = src_stats.get(e["site"], {"raw": 0, "kept": 0, "cost": 0})
    md.append(f"| {e['site']} | {site_status(e['site'])} | {st['raw']} | {st['kept']} | {round(st['cost'],4)} |")
for b in C.BLOCKED_SITES:
    md.append(f"| {b['site']} | BLOCKED | — | — | {b['reason']} |")
md.append("")

md.append("## 7. Guardrails & governance applied\n")
md.append("- **Budget governor** reads real account spend before/after every actor run; "
          f"soft-stops new runs at ${C.SESSION_SOFT_CEILING_USD}, hard-aborts at ${C.SESSION_HARD_ABORT_USD}, "
          f"absolute abort at ${C.ACCOUNT_ABS_ABORT_USD} (under the $5 platform cap).")
md.append("- **AI-role filter**: only titles matching the AI/ML taxonomy are kept; "
          "healthcare, finance, sales, HR, civil/mech, generic SWE explicitly excluded.")
md.append("- **Per-actor item caps** prevent any single scraper from draining the budget.")
md.append("- **Cross-source dedup** on (title, company) so Google Jobs / LinkedIn / Indeed overlaps aren't double-counted.")
md.append("- **7-day retention mitigated**: all raw + processed data exported locally on capture.")
md.append("")

md.append("## 8. Limitations (read before presenting)\n")
md.append("- FREE-plan $5 cap → this is a **representative sample, not a census**. Counts show *relative* demand, not absolute market size.")
md.append("- Many India listings omit dates → 'undated' rows are kept (dropping them would bias the sample); treat trend as *recent-activity* signal.")
md.append("- Company-tier is rubric-based; unknown employers are honestly labelled **Unclassified**, not guessed.")
md.append("- HackerNews 'Who is Hiring' is **global** and parsed from free text → low-weight, flagged separately.")
md.append("- Third-party actors can change output schemas; figures are reproducible from the saved raw JSON.")
md.append("")

open(os.path.join(OUT, "REPORT.md"), "w", encoding="utf-8").write("\n".join(md))
print("Wrote", os.path.join(OUT, "REPORT.md"))
print("Wrote", csv_path)
