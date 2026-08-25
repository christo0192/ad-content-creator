"""Shared config for the Market Research Agent (all tabs).

Reuses the same BigQuery target + Apify FREE acct #2 as the job-market agent.
LLM calls go through `claude -p` (Max plan) — no API key. See
memory market-research-llm-via-claude-cli.
"""
from __future__ import annotations
import os, shutil
from datetime import date, timedelta

# ---- run identity / cadence ----------------------------------------------
REPORT_DATE = date.today()
# Tab1/2/4 = weekly window; Tab3 jobs = monthly (its own package).
WEEKLY_WINDOW_DAYS = int(os.getenv("MR_WEEKLY_WINDOW_DAYS", "7"))
WEEKLY_WINDOW_START = REPORT_DATE - timedelta(days=WEEKLY_WINDOW_DAYS)
RUN_ID = f"weekly-{REPORT_DATE:%Y-%m-%d}"

# ---- BigQuery -------------------------------------------------------------
BQ_PROJECT  = os.getenv("MR_BQ_PROJECT", "ik-marketing-data")
BQ_DATASET  = os.getenv("MR_BQ_DATASET", "Market_Research")   # production dataset (provisioned 2026-06-25)
BQ_LOCATION = os.getenv("MR_BQ_LOCATION", "US")
BQ_SA_KEY   = os.getenv("MR_BQ_KEY", r"C:\Users\Admin\.gcp-keys\market-research-bq.json")
# Table per tab (run_date-partitioned snapshots, same dataset).
TABLES = {
    "social":      os.getenv("MR_TBL_SOCIAL",     "social_trends"),
    "blog":        os.getenv("MR_TBL_BLOG",       "blog_publications"),
    "competitor":  os.getenv("MR_TBL_COMPETITOR", "competitor_intel"),
    "exec":        os.getenv("MR_TBL_EXEC",       "executive_summary"),
}

def fqtn(key: str) -> str:
    return f"{BQ_PROJECT}.{BQ_DATASET}.{TABLES[key]}"

# ---- LLM (claude -p, Max plan) -------------------------------------------
CLAUDE_BIN = (os.getenv("CLAUDE_BIN") or shutil.which("claude")
              or r"C:\Users\Admin\.local\bin\claude.exe")
# Hybrid model split (2026-08): the bulk blog/competitor calls are mechanical
# page->JSON extraction, so they run on fast/cheap Haiku at low effort. Only the
# single exec-summary call is cross-dataset reasoning, so it runs on Sonnet 5 at
# medium effort. Invoked headless: claude -p --model <M> --effort <E> --output-format text
EXTRACT_MODEL  = os.getenv("MR_EXTRACT_MODEL", "haiku")            # Tab2/Tab4 page->JSON
SYNTH_MODEL    = os.getenv("MR_SYNTH_MODEL", "claude-sonnet-5")    # Exec Summary
EXTRACT_EFFORT = os.getenv("MR_EXTRACT_EFFORT", "low")    # mechanical extraction
SYNTH_EFFORT   = os.getenv("MR_SYNTH_EFFORT", "medium")   # reasoning / synthesis
LLM_TIMEOUT_S  = int(os.getenv("MR_LLM_TIMEOUT_S", "300"))
# `claude -p` spawns a full Node+agent process per call; even 2 concurrent heavy
# calls thrash a laptop CPU so both stall past their timeout. Sequential (1) is
# the reliable choice locally — with batching that's only a handful of calls.
# Raise on Fly where the container has dedicated CPU.
LLM_MAX_CONCURRENCY = int(os.getenv("MR_LLM_CONCURRENCY", "1"))

# ---- Apify (Reddit, FREE acct #2) ----------------------------------------
# Token from APIFY_TOKEN env. HARD ceiling = $1 per the user's cap (the governor
# refuses to launch once session spend hits this). The governor can't abort
# mid-run, so we ALSO cap items per run (MR_REDDIT_MAX) and probe small first.
APIFY_SOFT_CEILING_USD = float(os.getenv("MR_APIFY_SOFT", "0.50"))
APIFY_HARD_ABORT_USD   = float(os.getenv("MR_APIFY_HARD", "1.00"))   # hard $1 cap
APIFY_ACCOUNT_ABS_ABORT_USD = float(os.getenv("MR_APIFY_ABS", "4.50"))
APIFY_POLL_INTERVAL_S = 5
APIFY_DEFAULT_TIMEOUT_S = 240

# ---- IK curriculum context (for Tab2 curriculum-match + Tab4 gaps) --------
# Parsed coverage from the prior emerging-roles run; used as grounding context.
IK_CURRICULUM_JSON = os.getenv(
    "MR_IK_CURRICULUM",
    os.path.join(os.path.dirname(__file__), "..", "..", "ai-hiring-trends-test",
                 "output", "curriculum_coverage.json"))

HTTP_TIMEOUT_S = 30
USER_AGENT = "IK-MarketResearch/1.0 (+https://interviewkickstart.com; research bot)"
