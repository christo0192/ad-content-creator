"""Governed Naukri + LinkedIn scrape for emerging-AI-role discovery ($2.5 cap).
Captures description text for downstream skills extraction. LinkedIn first
(cheap breadth) then Naukri to the soft ceiling. Corrected cost priors."""
import os, sys, json, io, re
import config as C
import harness as H
import normalize as N
import classify as K
import emerging_config as E

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
HERE = os.path.dirname(__file__); RAW = os.path.join(HERE, "raw"); OUT = os.path.join(HERE, "output")

C.SESSION_SOFT_CEILING_USD = 2.20
C.SESSION_HARD_ABORT_USD = 2.50
HARD = 2.50

# (source, actor, builder, queries, count, worst_case_per_run)
SRCS = [
    ("LinkedIn Jobs", "curious_coder/linkedin-jobs-scraper", C._linkedin_input, E.LINKEDIN_QUERIES, 50, 0.12),
    ("Naukri",        "muhammetakkurtt/naukri-job-scraper",  C._naukri_input,   E.NAUKRI_QUERIES,   50, 0.30),
]


def desc_of(source, item):
    if "linkedin" in source.lower():
        return str(item.get("descriptionText", ""))[:1500]
    if "naukri" in source.lower():
        jd = item.get("jobDetails", {}) if isinstance(item.get("jobDetails"), dict) else {}
        return str(jd.get("description", "") or jd.get("shortDescription", ""))[:1500]
    return ""


def main():
    gov = H.BudgetGovernor()
    C.ACCOUNT_ABS_ABORT_USD = gov.baseline + HARD
    rows, manifest = [], []

    for source, actor, build, queries, count, worst in SRCS:
        for q in queries:
            if gov.session_spent + worst > HARD or not gov.soft_ok():
                print(f"[GUARD-SKIP] {source}/{q} (spent ${gov.session_spent:.3f})")
                manifest.append({"source": source, "query": q, "skipped": "budget"})
                continue
            try:
                items, cost, meta = H.run_actor(actor, build(q, count), gov, f"{source}:{q}", timeout_s=240)
            except H.BudgetExceeded as e:
                print(f"[ABORT] {e}"); break
            except Exception as e:
                print(f"[ERR] {source}/{q}: {e}"); manifest.append({"source": source, "query": q, "error": str(e)}); continue
            if meta.get("error"):
                print(f"[LAUNCH-ERR] {source}/{q}: {meta['error'][:150]}")
                manifest.append({"source": source, "query": q, "launch_error": meta["error"][:200]}); continue

            safe = re.sub(r"[^A-Za-z0-9]+", "_", f"{source}_{q}")
            json.dump(items, open(os.path.join(RAW, f"emrg_{safe}.json"), "w", encoding="utf-8"), ensure_ascii=False)

            kept = 0
            for it in items:
                if not isinstance(it, dict):
                    continue
                row = N.normalize_row(source, it, C.REPORT_DATE)
                if not K.classify_role(row["title"])[0]:
                    continue
                pdate, _ = K.parse_posted(row["posted_raw"], C.REPORT_DATE)
                win = K.in_window(pdate, C.WINDOW_START, C.REPORT_DATE)
                sc = E.score_title(row["title"])
                row.update({
                    "query": q,
                    "canonical": E.canonicalize(row["title"]),
                    "desc": desc_of(source, it),
                    "posted_date": pdate.isoformat() if pdate else "",
                    "window": ("in" if win else "out") if win is not None else "unknown",
                    **sc,
                })
                rows.append(row); kept += 1
            print(f"[OK] {source:<14}{q:<28} raw={meta['n_items']:<4} AI={kept:<4} "
                  f"cost=${meta['cost_usd']:<8} session=${meta['session_spent']}")
            manifest.append({"source": source, "query": q, "raw": meta["n_items"],
                             "kept_ai": kept, "cost_usd": meta["cost_usd"]})

    json.dump(rows, open(os.path.join(OUT, "emerging_rows.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump({"manifest": manifest,
               "governor": {"baseline": gov.baseline, "session_spent": gov.session_spent, "final_usage": gov.last},
               "window": {"start": C.WINDOW_START.isoformat(), "report_date": C.REPORT_DATE.isoformat()}},
              open(os.path.join(OUT, "emerging_manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n### kept AI rows: {len(rows)} | spend ${gov.session_spent:.4f} | usage ${gov.last:.4f}/$5")


if __name__ == "__main__":
    main()
