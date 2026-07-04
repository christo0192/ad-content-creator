"""Aggregate scraped rows for the emerging-roles gap analysis.
Produces output/emerging_aggregates.json (+ console summary) consumed by the
report and by Claude's evidence-backed synthesis."""
import os, json, io, sys
from collections import Counter, defaultdict
import emerging_config as E

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
OUT = os.path.join(os.path.dirname(__file__), "output")

rows = json.load(open(os.path.join(OUT, "emerging_rows.json"), encoding="utf-8"))
cov = json.load(open(os.path.join(OUT, "curriculum_coverage.json"), encoding="utf-8"))
cov_blob = json.dumps({k: cov.get(k) for k in ("covered_roles", "covered_skills", "covered_tools")}).lower()

# skills extraction per row (from description)
for r in rows:
    r["skills"] = E.extract_skills(r.get("desc", ""))


def companies_for(pred, n=6):
    c = Counter(r["company"] for r in rows if pred(r) and r.get("company"))
    return [f"{k} ({v})" for k, v in c.most_common(n)]


def samples_for(pred, n=3):
    out, seen = [], set()
    for r in rows:
        if pred(r) and r["title"] not in seen:
            out.append(r["title"]); seen.add(r["title"])
        if len(out) >= n:
            break
    return out


# Emerging (lens 1) buckets
em_counts = Counter(r["emerging_bucket"] for r in rows if r.get("emerging_bucket"))
emerging_buckets = []
for b, cnt in em_counts.most_common():
    inwin = sum(1 for r in rows if r.get("emerging_bucket") == b and r.get("window") == "in")
    # naive coverage guess (refined by Claude in synthesis)
    key = b.split("/")[0].split("(")[0].strip().lower()
    guess = "covered" if key and key in cov_blob else "gap"
    emerging_buckets.append({"bucket": b, "count": cnt, "in_window": inwin,
                             "coverage_guess": guess,
                             "companies": companies_for(lambda r, b=b: r.get("emerging_bucket") == b),
                             "samples": samples_for(lambda r, b=b: r.get("emerging_bucket") == b)})

# Seniority (lens 4)
sr_counts = Counter(r["seniority_bucket"] for r in rows if r.get("seniority_bucket"))
seniority_buckets = [{"bucket": b, "count": c,
                      "companies": companies_for(lambda r, b=b: r.get("seniority_bucket") == b),
                      "samples": samples_for(lambda r, b=b: r.get("seniority_bucket") == b)}
                     for b, c in sr_counts.most_common()]

# Novel / unmapped (light lens 2)
novel_rows = [r for r in rows if "novel_unmapped" in r.get("lenses", [])]
nov_counts = Counter(r["canonical"] for r in novel_rows if r.get("canonical"))
novel_titles = [{"canonical": k, "count": v,
                 "sample": next((r["title"] for r in novel_rows if r["canonical"] == k), ""),
                 "companies": companies_for(lambda r, k=k: r.get("canonical") == k, 4)}
                for k, v in nov_counts.most_common(40)]

# Top canonical titles overall
top_canon = Counter(r["canonical"] for r in rows if r.get("canonical"))

# Skills demand
skill_counts = Counter(s for r in rows for s in r.get("skills", []))
n = len(rows) or 1
skills_demand = [{"skill": k, "count": v, "pct": round(100 * v / n, 1),
                  "in_curriculum": k.lower() in cov_blob or any(t in cov_blob for t in k.lower().split("/"))}
                 for k, v in skill_counts.most_common(30)]

agg = {
    "n_rows": len(rows),
    "n_in_window": sum(1 for r in rows if r.get("window") == "in"),
    "by_source": dict(Counter(r["source"] for r in rows)),
    "lens_counts": {
        "L1_genai_emerging": sum(1 for r in rows if "L1_genai_emerging" in r.get("lenses", [])),
        "L4_seniority_hybrid": sum(1 for r in rows if "L4_seniority_hybrid" in r.get("lenses", [])),
        "novel_unmapped": len(novel_rows),
    },
    "emerging_buckets": emerging_buckets,
    "seniority_buckets": seniority_buckets,
    "novel_titles": novel_titles,
    "top_canonical": [{"title": k, "count": v} for k, v in top_canon.most_common(30)],
    "skills_demand": skills_demand,
}
json.dump(agg, open(os.path.join(OUT, "emerging_aggregates.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

print(f"rows={agg['n_rows']} in_window={agg['n_in_window']} by_source={agg['by_source']}")
print(f"lens: {agg['lens_counts']}")
print("\nEMERGING buckets:")
for b in emerging_buckets:
    print(f"  {b['bucket']:<36} n={b['count']:<4} win={b['in_window']:<4} guess={b['coverage_guess']}")
print("\nSENIORITY/hybrid:")
for b in seniority_buckets:
    print(f"  {b['bucket']:<28} n={b['count']}")
print(f"\nNOVEL/unmapped distinct canonical titles: {len(novel_titles)} (top shown in json)")
print("\nTop skills in demand:")
for s in skills_demand[:15]:
    print(f"  {s['skill']:<20} {s['count']:<4} {s['pct']}%  in_curriculum={s['in_curriculum']}")
print("\nSaved -> output/emerging_aggregates.json")
