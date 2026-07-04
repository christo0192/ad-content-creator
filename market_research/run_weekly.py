"""Weekly orchestrator — Market Research Agent.

Dispatches the weekly worker agents (Social, Blog, Competitor), each of which
fetches -> extracts -> validates against its Pydantic schema (the tool-call
gate). The orchestrator writes each validated tab to BigQuery, then synthesizes
the Executive Summary (Sonnet) over all 4 tabs (Job-Market read from its latest
monthly BQ snapshot) and writes that too.

  python run_weekly.py                 # full run -> BigQuery
  python run_weekly.py --no-bq         # collect + synthesize, skip BQ writes
  python run_weekly.py --only social   # run one agent
  python run_weekly.py --no-exec       # skip Executive Summary

LLM calls use `claude -p` (Max plan). Jobs (Tab 3) runs on its own monthly
cadence in ../job_market_agent.
"""
from __future__ import annotations
import os, sys, json, argparse, time
from datetime import datetime, timezone
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "shared"))
sys.path.insert(0, os.path.join(HERE, "agents"))

import config as C
import agent_social, agent_blog, agent_competitor
import exec_summary
OUT = os.path.join(HERE, "output")

AGENTS = {
    "social": agent_social,
    "blog": agent_blog,
    "competitor": agent_competitor,
}


def run(only=None, no_bq=False, no_exec=False):
    os.makedirs(OUT, exist_ok=True)
    rid = C.RUN_ID
    print(f"=== Market Research weekly | run_id={rid} | window {C.WEEKLY_WINDOW_START} -> {C.REPORT_DATE} ===")
    collected, summary = {}, {"run_id": rid, "generated_at": datetime.now(timezone.utc).isoformat(),
                              "tabs": {}}
    keys = [only] if only else list(AGENTS)
    for key in keys:
        t0 = time.time()
        try:
            rows = AGENTS[key].collect(rid)
        except Exception as e:
            print(f"[{key}] ERROR: {e}")
            summary["tabs"][key] = {"error": str(e)[:200]}
            continue
        collected[key] = rows
        bq_res = None
        if not no_bq and rows:
            import bq as BQ
            bq_res = BQ.write_snapshot(key, [r.to_bq() for r in rows], rid)
        print(f"[{key}] {len(rows)} rows | {time.time()-t0:.0f}s | bq={bq_res}")
        summary["tabs"][key] = {"rows": len(rows), "secs": round(time.time()-t0, 1), "bq": bq_res}
        # local snapshot
        json.dump([r.to_bq() for r in rows],
                  open(os.path.join(OUT, f"{key}_rows.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)

    # Executive Summary across whatever tabs we have
    if not no_exec and not only:
        t0 = time.time()
        ex_rows = exec_summary.synthesize(
            collected.get("social", []), collected.get("blog", []),
            collected.get("competitor", []), rid)
        bq_res = None
        if not no_bq and ex_rows:
            import bq as BQ
            bq_res = BQ.write_snapshot("exec", [r.to_bq() for r in ex_rows], rid)
        print(f"[exec] {len(ex_rows)} priorities | {time.time()-t0:.0f}s | bq={bq_res}")
        summary["tabs"]["exec"] = {"rows": len(ex_rows), "secs": round(time.time()-t0, 1), "bq": bq_res}
        json.dump([r.to_bq() for r in ex_rows],
                  open(os.path.join(OUT, "exec_rows.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)

    json.dump(summary, open(os.path.join(OUT, "weekly_manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n### done. manifest -> output/weekly_manifest.json")
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=list(AGENTS))
    ap.add_argument("--no-bq", action="store_true")
    ap.add_argument("--no-exec", action="store_true")
    a = ap.parse_args()
    run(only=a.only, no_bq=a.no_bq, no_exec=a.no_exec)
