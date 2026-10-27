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
  python run_weekly.py --preflight     # secrets + BQ SELECT 1 + one tiny claude -p
                                       #   call per LLM tier (extract + synth), then
                                       #   exit; no collection, no writes

LLM calls use `claude -p` (Max plan). Jobs (Tab 3) runs on its own monthly
cadence in ../job_market_agent. On Fly this runs MONTHLY (MR_CADENCE=monthly,
run_id monthly-YYYY-MM), started by the Cloudflare Worker ik-intelligence-trigger
on the 2nd — the file name is historical.

Exit codes (added 2026-10-27; before, a run with no LLM token wrote nothing
and still exited 0, so the Worker-started machine looked healthy):
  0  every tab that ran produced rows (and the Executive Summary, on a full run)
  1  degraded: a tab errored or produced 0 rows, or an uncaught error
  2  preflight failed (missing BQ creds / LLM token on Fly, or the --preflight
     BQ / claude -p probe failed) — nothing was collected or written
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
    print(f"=== Market Research {C.CADENCE} | run_id={rid} | window {C.WEEKLY_WINDOW_START} -> {C.REPORT_DATE} ===")
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


# ---------------------------------------------------------------------------
# Preflight + run verdict (added 2026-10-27). Checks report NAMES, never values.
# ---------------------------------------------------------------------------
PREFLIGHT_BQ = "BigQuery SA creds (MARKET_RESEARCH_BQ_SA_B64 | MARKET_RESEARCH_BQ_SA_JSON | MR_BQ_KEY file)"
PREFLIGHT_LLM = "CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY"


def _bq_creds_resolvable() -> bool:
    """True if bq can load an SA key, or GOOGLE_APPLICATION_CREDENTIALS names an
    existing key file. A malformed secret counts as missing; its exception text
    is not surfaced (it could quote part of the secret)."""
    import bq as BQ   # ImportError (no google-cloud-bigquery) stays loud
    try:
        if BQ._load_sa_info() is not None:
            return True
    except Exception:
        return False
    adc = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    return bool(adc and os.path.isfile(adc))


def _llm_token_required() -> bool:
    # Locally `claude` uses its own logged-in session, so only demand an env
    # token where there is none: on Fly (FLY_APP_NAME is set on every machine)
    # or when explicitly asked.
    return bool(os.getenv("FLY_APP_NAME")) or os.getenv("MR_REQUIRE_LLM_TOKEN") == "1"


def preflight(no_bq: bool, only: str | None = None) -> list[str]:
    """Names of missing runtime requirements ([] = good to go). Without the LLM
    token every claude -p call fails, blog/competitor/exec come back empty and
    the run used to exit 0 with nothing written. Social is the one LLM-free
    agent, so `--only social` skips the token check."""
    missing = []
    if not no_bq and not _bq_creds_resolvable():
        missing.append(PREFLIGHT_BQ)
    if (only != "social" and _llm_token_required()
            and not (os.getenv("CLAUDE_CODE_OAUTH_TOKEN") or os.getenv("ANTHROPIC_API_KEY"))):
        missing.append(PREFLIGHT_LLM)
    return missing


def run_problems(summary: dict, only=None, no_exec=False) -> list[str]:
    """Why a run is degraded ([] = healthy). Every tab that ran must have
    produced rows without an error, and a full run must include the Executive
    Summary. (Social 0 rows is flagged too — it means every free source failed.)"""
    tabs = summary.get("tabs", {})
    problems = []
    for key, tab in tabs.items():
        if tab.get("error"):
            problems.append(f"{key}: error {str(tab['error'])[:120]}")
        elif tab.get("rows", 0) == 0:
            problems.append(f"{key}: 0 rows")
    if not only and not no_exec and "exec" not in tabs:
        problems.append("exec: 0 rows")
    return problems


def run_ok(summary: dict, only=None, no_exec=False) -> bool:
    return not run_problems(summary, only, no_exec)


def run_preflight_only(no_bq: bool, only: str | None = None) -> int:
    """`--preflight`: prove the booted machine has its secrets, that BigQuery
    auth works (SELECT 1) and that `claude -p` answers on BOTH LLM tiers (one
    tiny call each, with the model AND effort the run uses, so a bad
    MR_*_MODEL / MR_*_EFFORT fails here instead of in the monthly run), then
    exit — no collection, no BQ write. Post-deploy smoke on Fly (DEPLOY_FLY.md)."""
    missing = preflight(no_bq, only)
    if missing:
        print("FATAL preflight: missing " + ", ".join(missing))
        return 2
    if not no_bq:
        try:
            import bq as BQ
            BQ.client().query("SELECT 1").result()
        except Exception as e:
            print(f"FATAL preflight: BigQuery auth/query failed: {type(e).__name__}: {str(e)[:200]}")
            return 2
        print(f"[preflight] BigQuery OK (project {C.BQ_PROJECT})")
    if only != "social":
        import llm as L
        for tier, model, effort in (("extract", C.EXTRACT_MODEL, C.EXTRACT_EFFORT),
                                    ("synth", C.SYNTH_MODEL, C.SYNTH_EFFORT)):
            try:
                out = L.claude("Reply with OK", model=model, timeout=120, effort=effort)
            except Exception as e:
                print(f"FATAL preflight: claude -p failed ({tier} {model}/{effort}): "
                      f"{type(e).__name__}: {str(e)[:200]}")
                return 2
            print(f"[preflight] claude -p OK ({tier} {model}/{effort}): {out[:40]!r}")
    print("preflight OK")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=list(AGENTS))
    ap.add_argument("--no-bq", action="store_true")
    ap.add_argument("--no-exec", action="store_true")
    ap.add_argument("--preflight", action="store_true",
                    help="check secrets, BigQuery (SELECT 1) and one claude -p call per "
                         "LLM tier, print 'preflight OK', exit; collects and writes nothing")
    a = ap.parse_args(argv)
    if a.preflight:
        return run_preflight_only(a.no_bq, a.only)
    missing = preflight(a.no_bq, a.only)
    if missing:
        print("FATAL preflight: missing " + ", ".join(missing))
        return 2
    s = run(only=a.only, no_bq=a.no_bq, no_exec=a.no_exec)
    problems = run_problems(s, a.only, a.no_exec)
    if problems:
        print("[FATAL] run degraded: " + "; ".join(problems))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
