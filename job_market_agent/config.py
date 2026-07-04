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
# Monthly run -> look back ~1 month (32d buffer covers slipped run dates).
# REPORT_DATE is dynamic (today) so the agent is self-dating each month.
# ---------------------------------------------------------------------------
REPORT_DATE = date.today()
WINDOW_DAYS = 32
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
