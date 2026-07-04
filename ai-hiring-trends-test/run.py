"""Scaled, governed run: scrape -> normalize -> AI-filter -> tier -> date-tag -> dedup.
Writes output/processed.json (kept rows) + output/manifest.json (per-run costs).
Re-running reporting (report.py) does NOT require re-scraping."""
import os, json, re, sys, io
import config as C
import harness as H
import normalize as N
import classify as K

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
HERE = os.path.dirname(__file__)
RAW = os.path.join(HERE, "raw")
OUT = os.path.join(HERE, "output")
os.makedirs(RAW, exist_ok=True); os.makedirs(OUT, exist_ok=True)


def norm_key(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def main():
    gov = H.BudgetGovernor()
    manifest = []
    all_rows = []

    for entry in C.ROSTER:
        site = entry["site"]
        if not gov.soft_ok():
            manifest.append({"site": site, "skipped": "soft budget ceiling reached"})
            print(f"[SKIP] {site}: soft budget ceiling (${gov.session_spent:.3f})")
            continue
        for q in entry["queries"]:
            if not gov.soft_ok():
                print(f"[SKIP] {site}/{q}: soft ceiling")
                break
            label = f"{site}:{q}"
            try:
                run_input = entry["build_input"](q, entry["scale_max_items"])
                items, cost, meta = H.run_actor(entry["actor"], run_input, gov, label,
                                                 timeout_s=C.DEFAULT_TIMEOUT_S)
            except H.BudgetExceeded as e:
                print(f"[BUDGET-ABORT] {label}: {e}")
                manifest.append({"site": site, "query": q, "aborted": str(e)})
                gov_dump(gov, manifest, all_rows); return
            except Exception as e:
                print(f"[ERR] {label}: {e}")
                manifest.append({"site": site, "query": q, "error": str(e)})
                continue

            if meta.get("error"):
                print(f"[LAUNCH-ERR] {label}: {meta['error'][:160]}")
                manifest.append({"site": site, "query": q, "launch_error": meta["error"][:300]})
                continue

            safe = re.sub(r"[^A-Za-z0-9]+", "_", f"{site}_{q}")
            with open(os.path.join(RAW, f"scaled_{safe}.json"), "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False)

            kept = 0
            for it in items:
                if not isinstance(it, dict):
                    continue
                row = N.normalize_row(site, it, C.REPORT_DATE)
                keep, bucket, fam, fam_name = K.classify_role(row["title"])
                if not keep:
                    continue
                pdate, praw = K.parse_posted(row["posted_raw"], C.REPORT_DATE)
                win = K.in_window(pdate, C.WINDOW_START, C.REPORT_DATE)
                row.update({
                    "role_bucket": bucket,
                    "family_code": fam,
                    "family": fam_name,
                    "company_tier": K.classify_tier(row["company"]),
                    "salary_norm": K.normalize_salary(row["salary"]),
                    "posted_date": pdate.isoformat() if pdate else "",
                    "window": ("in" if win else "out") if win is not None else "unknown",
                    "query": q,
                })
                all_rows.append(row)
                kept += 1

            print(f"[OK] {label:<42} raw={meta['n_items']:<4} kept_AI={kept:<4} "
                  f"cost=${meta['cost_usd']:<7} session=${meta['session_spent']}")
            manifest.append({"site": site, "query": q, "raw": meta["n_items"],
                             "kept_ai": kept, "cost_usd": meta["cost_usd"],
                             "status": meta["status"]})

    gov_dump(gov, manifest, all_rows)


def gov_dump(gov, manifest, all_rows):
    # Cross-source dedup
    seen = {}
    deduped = []
    dup = 0
    for r in all_rows:
        key = (norm_key(r["title"]), norm_key(r["company"]))
        if not key[0]:
            deduped.append(r); continue
        if key in seen:
            dup += 1
            seen[key]["dup_sources"] = sorted(set(seen[key].get("dup_sources", [seen[key]["source"]]) + [r["source"]]))
            continue
        seen[key] = r
        deduped.append(r)

    with open(os.path.join(OUT, "processed.json"), "w", encoding="utf-8") as f:
        json.dump(deduped, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"manifest": manifest,
                   "governor": {"baseline": gov.baseline, "session_spent": gov.session_spent,
                                "final_usage": gov.last, "events": gov.events},
                   "window": {"start": C.WINDOW_START.isoformat(),
                              "report_date": C.REPORT_DATE.isoformat()}},
                  f, ensure_ascii=False, indent=2)

    print("\n" + "#" * 60)
    print(f"TOTAL kept AI rows (pre-dedup): {len(all_rows)}  | after dedup: {len(deduped)}  | dups removed: {dup}")
    print(f"SESSION SPEND: ${gov.session_spent:.4f}  | FINAL MONTHLY USAGE: ${gov.last:.4f} / $5.00")
    print(f"Saved -> output/processed.json , output/manifest.json")


if __name__ == "__main__":
    main()
