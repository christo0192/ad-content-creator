"""$0.50-capped smoke test: measure REAL cost-per-row for the 5 not-yet-run sites.
Fixes last time's failure with a PREDICTIVE guard: a run is skipped unless
(session_spent + worst_case_for_that_actor) stays under the hard cap -> no single
run can overshoot $0.50. Naukri first (biggest unknown). $0 if budget exhausts."""
import os, sys, json, io
import config as C
import harness as H
import normalize as N
import classify as K

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
HERE = os.path.dirname(__file__)
RAW = os.path.join(HERE, "raw"); OUT = os.path.join(HERE, "output")

# ---- tighten ceilings for the smoke test ----
C.SESSION_SOFT_CEILING_USD = 0.40
C.SESSION_HARD_ABORT_USD = 0.50

HARD_CAP = 0.50
# (site, actor, build_input, query, items, known_fixed_fee, worst_case_guard)
PLAN = [
    ("Naukri",     "muhammetakkurtt/naukri-job-scraper", C._naukri_input,  "Machine Learning Engineer", 50, 0.0,   0.30),
    ("Indeed",     "borderline/indeed-scraper",          C._indeed_input,  "Machine Learning Engineer", 5,  0.0,   0.05),
    ("HackerNews", "agency-shift/hackernews-jobs-ask-scraper", C._hn_input, "AI",                       5,  0.05,  0.07),
    ("Foundit",    "easyapi/foundit-jobs-scraper",       C._foundit_input, "Artificial Intelligence",   4,  0.09,  0.12),
    ("Glassdoor",  "valig/glassdoor-jobs-scraper",       C._glassdoor_input,"Data Scientist",           4,  0.0,   0.12),
]

gov = H.BudgetGovernor()
C.ACCOUNT_ABS_ABORT_USD = gov.baseline + HARD_CAP   # absolute backstop on new account
results = []

for site, actor, build, q, items, fixed, worst in PLAN:
    if gov.session_spent + worst > HARD_CAP:
        print(f"[GUARD-SKIP] {site}: would risk >${HARD_CAP} "
              f"(spent ${gov.session_spent:.3f} + worst ${worst}) -> skipped")
        results.append({"site": site, "skipped": "predictive guard", "cost": 0})
        continue
    print(f"\n=== SMOKE {site} ({actor}) items={items} ===")
    try:
        run_input = build(q, items)
        rows, cost, meta = H.run_actor(actor, run_input, gov, f"smoke:{site}", timeout_s=200)
    except H.BudgetExceeded as e:
        print(f"[BUDGET-ABORT] {site}: {e}"); break
    except Exception as e:
        print(f"[ERR] {site}: {e}"); results.append({"site": site, "error": str(e), "cost": 0}); continue

    if meta.get("error"):
        print(f"[LAUNCH-ERR] {site}: {meta['error'][:200]}")
        results.append({"site": site, "launch_error": meta["error"][:200], "cost": 0}); continue

    safe = site.replace(" ", "_")
    with open(os.path.join(RAW, f"smoke_{safe}.json"), "w", encoding="utf-8") as f:
        json.dump({"input": run_input, "meta": meta, "items": rows}, f, ensure_ascii=False, indent=2)

    n = meta["n_items"]
    kept = sum(1 for it in rows if isinstance(it, dict)
               and K.classify_role(N.normalize_row(site, it, C.REPORT_DATE)["title"])[0])
    per_item = (cost - fixed) / n if n else None
    print(f"  status={meta['status']} rows={n} kept_AI={kept} cost=${cost:.5f} "
          f"(fixed≈${fixed}, per_item≈${per_item:.5f})" if per_item is not None
          else f"  status={meta['status']} rows={n} cost=${cost:.5f}")
    results.append({"site": site, "actor": actor, "rows": n, "kept_ai": kept,
                    "cost": round(cost, 5), "known_fixed": fixed,
                    "per_item": round(per_item, 5) if per_item is not None else None})

# ---- summary + projections ----
print("\n" + "#" * 72)
print(f"{'Site':<12}{'rows':>5}{'AI':>4}{'cost$':>9}{'$/item':>9}{'~100 rows':>11}{'~500 rows':>11}")
for r in results:
    if "cost" in r and r.get("per_item") is not None:
        p = r["per_item"]; fx = r["known_fixed"]
        c100 = fx + p * 100; c500 = fx + p * 500
        print(f"{r['site']:<12}{r['rows']:>5}{r['kept_ai']:>4}{r['cost']:>9.4f}"
              f"{p:>9.4f}{c100:>11.3f}{c500:>11.3f}")
    else:
        note = r.get("skipped") or r.get("error") or r.get("launch_error") or "n/a"
        print(f"{r['site']:<12}  -> {note}")
print(f"\nTOTAL SMOKE SPEND: ${gov.session_spent:.4f} / ${HARD_CAP} cap "
      f"| final usage ${gov.last:.4f}")

with open(os.path.join(OUT, "smoke_costs.json"), "w", encoding="utf-8") as f:
    json.dump({"results": results, "spent": gov.session_spent, "baseline": gov.baseline,
               "final_usage": gov.last}, f, ensure_ascii=False, indent=2)
print("Saved -> output/smoke_costs.json")
