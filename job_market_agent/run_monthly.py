"""Job Market Demand agent — monthly LinkedIn run.

  python run_monthly.py            # LIVE: governed Apify LinkedIn scrape -> BQ
  python run_monthly.py --dry-run  # reuse existing raw LinkedIn JSON, no Apify
                                   #   spend, no token needed; still writes BQ
  python run_monthly.py --dry-run --no-bq   # process + validate only, skip BQ

Pipeline (per the v0.1 plan): fetch -> normalize -> AI-classify -> score ->
Pydantic-validate (the tool-call gate) -> dedup -> write BigQuery + local
snapshot + cost/validation manifest.
"""
from __future__ import annotations
import os, sys, io, re, json, glob, argparse
from datetime import datetime, timezone

import config as C
import normalize as N
import classify as K
import scoring as SC
from schema import JobDemandRow
from pydantic import ValidationError

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
RAW = os.path.join(HERE, "raw")
# Existing tested raw LinkedIn pulls live in the sibling test harness.
DRYRUN_RAW_GLOBS = [
    os.path.join(HERE, "..", "ai-hiring-trends-test", "raw", "emrg_LinkedIn_Jobs_*.json"),
    os.path.join(HERE, "..", "ai-hiring-trends-test", "raw", "scaled_LinkedIn_Jobs_*.json"),
]

# SOURCE / RUN_ID are set in main() from --source (default keeps LinkedIn).
SOURCE = "linkedin"
RUN_ID = f"linkedin-{C.REPORT_DATE:%Y-%m}"
NORMALIZERS = {"linkedin": N.normalize_linkedin, "naukri": N.normalize_naukri}


def _query_from_filename(path: str) -> str:
    base = os.path.basename(path)
    m = re.sub(r"^(emrg|scaled)_LinkedIn_Jobs_", "", base)
    m = re.sub(r"\.json$", "", m)
    return m.replace("_", " ").strip()


def build_row(query: str, item: dict) -> JobDemandRow | None:
    """Normalize -> AI-filter -> score -> validate. Returns a row or None if the
    title is non-AI (dropped) — raises ValidationError if it fails the gate."""
    base = NORMALIZERS[SOURCE](item)
    keep, bucket, fam_code, fam_name = K.classify_role(base["title"])
    if not keep:
        return None
    pdate, praw = K.parse_posted(base["posted_raw"], C.REPORT_DATE)
    win = K.in_window(pdate, C.WINDOW_START, C.REPORT_DATE)
    sc = SC.score_title(base["title"])
    skills = SC.extract_skills((base.get("description") or "") + " " + base["title"])
    smin, smax = K.parse_salary_inr(base.get("salary_raw"))

    return JobDemandRow(
        run_id=RUN_ID,
        run_date=C.REPORT_DATE,
        source=C.SOURCES[SOURCE]["name"],
        query=query,
        job_id=base.get("job_id") or None,
        title=base["title"],
        normalized_role=bucket,
        role_family=fam_name,
        company=base.get("company") or None,
        company_tier=K.classify_tier(base.get("company")),
        location=base.get("location") or None,
        seniority_level=base.get("seniority_level"),
        employment_type=base.get("employment_type"),
        job_function=base.get("job_function"),
        industries=base.get("industries"),
        applicants_count=base.get("applicants_count"),
        salary_raw=K.normalize_salary(base.get("salary_raw")) or None,
        salary_min_inr=smin,
        salary_max_inr=smax,
        posted_date=pdate,
        posted_raw=praw or None,
        in_window=win,
        emerging_bucket=sc["emerging_bucket"],
        seniority_bucket=sc["seniority_bucket"],
        canonical_bucket=sc["canonical_bucket"],
        is_emerging=sc["is_emerging"],
        lenses=sc["lenses"],
        skills=skills,
        reference_url=base.get("url") or None,
    )


def process(raw_by_query: dict[str, list[dict]]) -> tuple[list[JobDemandRow], dict]:
    rows: list[JobDemandRow] = []
    seen: set[str] = set()
    stats = {"raw": 0, "non_ai_dropped": 0, "validation_errors": 0,
             "duplicates": 0, "kept": 0, "by_query": {}}
    for query, items in raw_by_query.items():
        qk = {"raw": len(items), "kept": 0}
        for it in items:
            if not isinstance(it, dict):
                continue
            stats["raw"] += 1
            try:
                row = build_row(query, it)
            except ValidationError:
                stats["validation_errors"] += 1
                continue
            if row is None:
                stats["non_ai_dropped"] += 1
                continue
            key = row.job_id or f"{(row.title or '').lower()}|{(row.company or '').lower()}|{row.reference_url}"
            if key in seen:
                stats["duplicates"] += 1
                continue
            seen.add(key)
            rows.append(row)
            stats["kept"] += 1
            qk["kept"] += 1
        stats["by_query"][query] = qk
    return rows, stats


# ---------------------------------------------------------------------------
# Fetch modes
# ---------------------------------------------------------------------------
def fetch_dryrun() -> tuple[dict[str, list[dict]], dict]:
    by_query: dict[str, list[dict]] = {}
    files = []
    for g in DRYRUN_RAW_GLOBS:
        files += glob.glob(g)
    for f in sorted(set(files)):
        q = _query_from_filename(f)
        try:
            data = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, list):
            by_query.setdefault(q, []).extend(data)
    meta = {"mode": "dry-run", "files": len(files), "queries": list(by_query),
            "apify_cost_usd": 0.0}
    return by_query, meta


def fetch_live(limit_queries: int | None = None) -> tuple[dict[str, list[dict]], dict]:
    import harness as H   # imported lazily: requires APIFY_TOKEN
    src = C.SOURCES[SOURCE]
    actor, input_fn, sname = src["actor"], src["input"], src["name"]
    queries = list(src["queries"])
    if limit_queries:
        queries = queries[:limit_queries]
    gov = H.BudgetGovernor()
    by_query: dict[str, list[dict]] = {}
    manifest = []
    for q in queries:
        if gov.session_spent + C.WORST_CASE_PER_QUERY_USD > C.SESSION_HARD_ABORT_USD or not gov.soft_ok():
            print(f"[GUARD-SKIP] {q} (spent ${gov.session_spent:.3f})")
            manifest.append({"query": q, "skipped": "budget"})
            continue
        try:
            items, cost, meta = H.run_actor(
                actor, input_fn(q), gov, f"{sname}:{q}", timeout_s=240)
        except H.BudgetExceeded as e:
            print(f"[ABORT] {e}")
            break
        except Exception as e:
            print(f"[ERR] {q}: {e}")
            manifest.append({"query": q, "error": str(e)})
            continue
        if meta.get("error"):
            print(f"[LAUNCH-ERR] {q}: {meta['error'][:150]}")
            manifest.append({"query": q, "launch_error": meta["error"][:200]})
            continue
        safe = re.sub(r"[^A-Za-z0-9]+", "_", q)
        json.dump(items, open(os.path.join(RAW, f"live_{sname}_{safe}.json"), "w",
                  encoding="utf-8"), ensure_ascii=False)
        by_query.setdefault(q, []).extend(items)
        print(f"[OK] {q:<28} raw={meta['n_items']:<4} cost=${meta['cost_usd']:<8} "
              f"session=${meta['session_spent']}")
        manifest.append({"query": q, "raw": meta["n_items"], "cost_usd": meta["cost_usd"]})
    metaout = {"mode": "live", "source": sname, "apify_cost_usd": round(gov.session_spent, 5),
               "apify_final_usage": round(gov.last, 5), "manifest": manifest}
    return by_query, metaout


def main():
    global SOURCE, RUN_ID
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=list(C.SOURCES),
                    default=os.getenv("JOBMKT_SOURCE", "linkedin"),
                    help="job board to scrape (default: $JOBMKT_SOURCE or linkedin)")
    ap.add_argument("--limit-queries", type=int, default=None,
                    help="live only: cap number of queries (smoke test)")
    ap.add_argument("--dry-run", action="store_true",
                    help="reuse existing raw LinkedIn JSON; no Apify spend/token")
    ap.add_argument("--no-bq", action="store_true", help="skip the BigQuery write")
    args = ap.parse_args()

    SOURCE = args.source
    RUN_ID = f"{SOURCE}-{C.REPORT_DATE:%Y-%m}"

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(RAW, exist_ok=True)

    print(f"=== Job Market Demand agent | source={C.SOURCES[SOURCE]['name']} | "
          f"run_id={RUN_ID} | window {C.WINDOW_START} -> {C.REPORT_DATE} ===")
    by_query, fetch_meta = (fetch_dryrun() if args.dry_run
                            else fetch_live(args.limit_queries))
    rows, stats = process(by_query)

    print(f"\n[PROCESS] raw={stats['raw']} kept={stats['kept']} "
          f"non-AI-dropped={stats['non_ai_dropped']} dups={stats['duplicates']} "
          f"validation-errors={stats['validation_errors']}")

    bq_rows = [r.to_bq() for r in rows]
    json.dump(bq_rows, open(os.path.join(OUT, "job_demand_rows.json"), "w",
              encoding="utf-8"), ensure_ascii=False, indent=2)

    bq_result = None
    if not args.no_bq and bq_rows:
        import bigquery_writer as BW
        bq_result = BW.write_snapshot(bq_rows, RUN_ID, dry_run=args.dry_run)
        print(f"[BQ] loaded {bq_result['loaded']} rows -> {bq_result['table']} "
              f"(table now {bq_result['table_total_rows']} rows)")
        summ = BW.query_summary(RUN_ID)
        print("[BQ] demand-by-role (top 10):")
        for s in summ[:10]:
            print(f"     {s['normalized_role']:<32} n={s['n']:<4} "
                  f"emerging={s['emerging']:<4} in_window={s['in_window']}")

    manifest = {
        "run_id": RUN_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": {"start": C.WINDOW_START.isoformat(), "report_date": C.REPORT_DATE.isoformat()},
        "fetch": fetch_meta,
        "stats": stats,
        "bq": bq_result,
    }
    json.dump(manifest, open(os.path.join(OUT, "run_manifest.json"), "w",
              encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n### kept {len(rows)} rows | apify ${fetch_meta.get('apify_cost_usd', 0)} "
          f"| manifest -> output/run_manifest.json")


if __name__ == "__main__":
    main()
