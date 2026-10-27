"""Config for the production Job Market Demand agent (Tab 3 of the IK India
market-research workbook).

SCOPE LOCK (decided 2026-06-23): LinkedIn ONLY, run MONTHLY, store to BigQuery.
Naukri / Foundit / Glassdoor / Google Jobs are intentionally NOT used here.
The other three market-research agents keep their own separate plans.

No secrets in this file. APIFY_TOKEN comes from the environment at runtime
(use Apify account #2 `hip_bouncer`, FREE $5/mo cap).
"""
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# CADENCE / DATE WINDOW
# Default = rolling ~32-day lookback so an automated monthly cron (the
# Cloudflare Worker ik-intelligence-trigger starts the Fly machine on the 1st,
# 03:30 UTC) always captures a full month of postings regardless of the run day.
# REPORT_DATE is the container's UTC date, so the run_id label is the RUN month
# (naukri-2026-11 holds mostly October postings) — kept for continuity.
# REPORT_DATE is dynamic so the agent self-dates each month; postings are
# date-filtered post-hoc against this window (in_window).
# Overrides: JOBMKT_WINDOW_DAYS=N (lookback length) or JOBMKT_WINDOW_START=
# YYYY-MM-DD (explicit start, e.g. an ad-hoc month-to-date run).
# ---------------------------------------------------------------------------
import os as _os
REPORT_DATE = date.today()
WINDOW_DAYS = int(_os.getenv("JOBMKT_WINDOW_DAYS", "32"))
_ws = _os.getenv("JOBMKT_WINDOW_START")
if _ws:
    WINDOW_START = date.fromisoformat(_ws)
    WINDOW_DAYS = max(1, (REPORT_DATE - WINDOW_START).days)
else:
    WINDOW_START = REPORT_DATE - timedelta(days=WINDOW_DAYS)

# ---------------------------------------------------------------------------
# BUDGET GUARDRAILS  (sized for LinkedIn-only monthly ~ $0.70-1.00/run)
# LinkedIn actor measured ~$0.001/row. 14 queries x 50 rows ~= 700 rows ~ $0.70.
# Ceilings sit well under the account's $5 monthly cap with headroom for the
# largest single-run cost (the memory's hard lesson: keep
# soft_ceiling >= cap - largest_expected_single_run_cost).
# ---------------------------------------------------------------------------
SESSION_SOFT_CEILING_USD = 1.50   # stop launching NEW queries past this session delta
SESSION_HARD_ABORT_USD   = 2.00   # abort the whole run past this session delta
ACCOUNT_ABS_ABORT_USD    = 4.50   # abort if absolute monthly usage crosses this (buffer under $5)
WORST_CASE_PER_QUERY_USD = 0.15   # predictive guard: skip a query if it could cross HARD
# Coverage gate (2026-10-27): if fewer than this share of the planned queries
# returned data (the rest errored / were budget-skipped / never ran after an
# [ABORT]), a live run does NOT replace the month's BigQuery snapshot and exits
# 4; any smaller shortfall still writes but exits 5 (see run_monthly.py).
MIN_QUERY_SUCCESS_SHARE = 0.8

DEFAULT_TIMEOUT_S = 300
POLL_INTERVAL_S   = 5

# ---------------------------------------------------------------------------
# LINKEDIN SOURCE
# ---------------------------------------------------------------------------
LINKEDIN_ACTOR = "curious_coder/linkedin-jobs-scraper"
LINKEDIN_INDIA_GEOID = "102713980"        # LinkedIn geoId for India
COUNT_PER_QUERY = 50                       # rows per query (actor `count`)
SCRAPE_COMPANY = True                      # enrich with company fields (tier signal)
LINKEDIN_TPR_SECONDS = WINDOW_DAYS * 24 * 3600   # f_TPR=r<sec>: cap to window at source

# Comprehensive AI/ML query plan (core + emerging). Mirrors the validated
# emerging-roles run so month-over-month is comparable.
LINKEDIN_QUERIES = [
    "Generative AI", "Agentic AI", "AI Agent", "LLM Engineer",
    "Machine Learning Engineer", "Data Scientist", "AI Engineer",
    "MLOps Engineer", "Prompt Engineer", "RAG Engineer", "Applied AI",
    "AI Architect", "Computer Vision Engineer", "NLP Engineer",
]


def linkedin_input(query, count=COUNT_PER_QUERY):
    """Build the actor input dict for one India-scoped, window-capped query."""
    import urllib.parse as up
    url = ("https://www.linkedin.com/jobs/search/?keywords="
           + up.quote(query)
           + "&location=India&geoId=" + LINKEDIN_INDIA_GEOID
           + "&f_TPR=r" + str(LINKEDIN_TPR_SECONDS))
    return {"urls": [url], "count": count, "scrapeCompany": SCRAPE_COMPANY}


# ---------------------------------------------------------------------------
# NAUKRI SOURCE  (added 2026-08: India-native board, cheaper than LinkedIn.
# Actor: thirdwatch/naukri-jobs-scraper — PAY_PER_EVENT $0.001/result +
# $0.00005 start => ~$0.05 per 50-job query (~10x cheaper than the
# muhammetakkurtt detailed actor, whose `job_item_detailed` events cost
# ~$0.01/job). thirdwatch returns a FLAT 60-field payload with posted_date
# already ISO, a real skills list, and broken-out salary. `freshnessDays` caps
# recency at source; postings are still post-hoc filtered via in_window.)
# ---------------------------------------------------------------------------
NAUKRI_ACTOR = "thirdwatch/naukri-jobs-scraper"
# Legacy (expensive, nested payload) — kept for reference only:
NAUKRI_ACTOR_LEGACY = "muhammetakkurtt/naukri-job-scraper"
NAUKRI_COUNT_PER_QUERY = 50
# Nearest freshness enum ('0','1','3','7','15','30') at/above the MTD window.
NAUKRI_FRESHNESS_DAYS = "30" if WINDOW_DAYS > 15 else "15"
# Mirror the LinkedIn AI/ML query plan for month-over-month comparability.
NAUKRI_QUERIES = list(LINKEDIN_QUERIES)


def naukri_input(query, count=NAUKRI_COUNT_PER_QUERY):
    """Build the thirdwatch Naukri actor input for one AI/ML query (India)."""
    return {
        "platform": "naukri",
        "queries": [query],
        "location": "India",
        "includeNaukriDetails": True,
        "includeDescription": True,
        "maxResultsPerQuery": max(1, count),
        "freshnessDays": NAUKRI_FRESHNESS_DAYS,
        "sortBy": "date",
    }


# ---------------------------------------------------------------------------
# ACTIVE JOB SOURCE  (env/CLI selectable; default LinkedIn to preserve the
# original monthly contract). run_monthly.py --source naukri flips this.
# ---------------------------------------------------------------------------
SOURCES = {
    "linkedin": {"name": "LinkedIn", "actor": LINKEDIN_ACTOR,
                 "queries": LINKEDIN_QUERIES, "input": linkedin_input},
    "naukri":   {"name": "Naukri", "actor": NAUKRI_ACTOR,
                 "queries": NAUKRI_QUERIES, "input": naukri_input},
}


# ---------------------------------------------------------------------------
# BIGQUERY TARGET
# Auth: the `claude-code-dev-bq@` service account (project jobUser + dataViewer,
# dataEditor on cai_dev_sandbox / CAI / SIP datasets). It CANNOT create a new
# top-level dataset, so until the data team provisions a dedicated
# `Market_Research` dataset + grant, we land in the writable `cai_dev_sandbox`.
# Everything is env-overridable -> flip to Market_Research with one env var.
# ---------------------------------------------------------------------------
import os

BQ_PROJECT  = os.getenv("JOBMKT_BQ_PROJECT", "ik-marketing-data")
BQ_DATASET  = os.getenv("JOBMKT_BQ_DATASET", "Market_Research")   # production dataset (provisioned 2026-06-25)
BQ_TABLE    = os.getenv("JOBMKT_BQ_TABLE", "job_market_demand")
BQ_LOCATION = os.getenv("JOBMKT_BQ_LOCATION", "US")
BQ_SA_KEY   = os.getenv("JOBMKT_BQ_KEY", r"C:\Users\Admin\.gcp-keys\market-research-bq.json")
BQ_FQTN = f"{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}"
