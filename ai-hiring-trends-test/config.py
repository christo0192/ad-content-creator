"""Central config for the AI-hiring-trends test harness.
Geography = India. Roles = all four AI families. Budget = FREE plan $5 cap.
No secrets here — token comes from APIFY_TOKEN env var at runtime.
"""
from datetime import date, timedelta

# ----------------------------------------------------------------------------
# GOVERNANCE / BUDGET GUARDRAILS
# ----------------------------------------------------------------------------
# Apify account hard platform cap is $5.00/mo (maxMonthlyUsageUsd). We layer our
# own, tighter ceilings on top, enforced by the runtime budget governor.
SESSION_SOFT_CEILING_USD = 4.00   # stop launching NEW scaled runs past this session delta
SESSION_HARD_ABORT_USD   = 4.50   # abort the whole pipeline immediately past this session delta
ACCOUNT_ABS_ABORT_USD    = 4.80   # abort if absolute monthly usage crosses this (buffer under $5)

# Per-run safety so a single misbehaving actor cannot drain the budget.
PROBE_MAX_ITEMS   = 10            # calibration probe size
DEFAULT_TIMEOUT_S = 300          # per-actor run timeout (secs)
POLL_INTERVAL_S   = 5

# ----------------------------------------------------------------------------
# DATE WINDOW  (last 2 months relative to report date 2026-06-17)
# ----------------------------------------------------------------------------
REPORT_DATE  = date(2026, 6, 17)
WINDOW_DAYS  = 62
WINDOW_START = REPORT_DATE - timedelta(days=WINDOW_DAYS)   # 2026-04-16

# ----------------------------------------------------------------------------
# AI ROLE SEARCH QUERIES  (India)
# Sent to each actor so most scraped rows are already AI-relevant -> max rows/$.
# ----------------------------------------------------------------------------
AI_QUERIES = [
    "Machine Learning Engineer",
    "Data Scientist",
    "AI Engineer",
    "MLOps Engineer",
    "Generative AI Engineer",
    "LLM Engineer",
    "Computer Vision Engineer",
    "NLP Engineer",
    "Data Engineer",
    "AI Architect",
]
# Lean query set for pricier actors (fewer queries -> lower spend).
AI_QUERIES_LEAN = [
    "Machine Learning Engineer",
    "Data Scientist",
    "AI Engineer",
    "Generative AI",
]

INDIA_LOCATION = "India"
LINKEDIN_INDIA_GEOID = "102713980"   # LinkedIn geoId for India
# f_TPR=r<seconds>: cap LinkedIn results to last 62 days at source
LINKEDIN_TPR_SECONDS = WINDOW_DAYS * 24 * 3600

# ----------------------------------------------------------------------------
# ACTOR ROSTER  (only free-plan-runnable PAY_PER_EVENT actors)
# `build_input(query, max_items)` returns the actor-specific input dict.
# `price_known` per-item USD if known from metadata, else None -> calibrate.
# ----------------------------------------------------------------------------

def _linkedin_input(query, max_items):
    import urllib.parse as up
    url = ("https://www.linkedin.com/jobs/search/?keywords="
           + up.quote(query)
           + "&location=India&geoId=" + LINKEDIN_INDIA_GEOID
           + "&f_TPR=r" + str(LINKEDIN_TPR_SECONDS))
    return {"urls": [url], "count": max_items, "scrapeCompany": True}

def _google_input(query, max_items):
    return {"query": query, "location": INDIA_LOCATION, "country": "in",
            "num_results": max_items, "max_pagination": 0}

def _naukri_input(query, max_items):
    # maxJobs has a hard minimum of 50 on this actor. Keep inputs minimal to
    # avoid enum-validation 400s; date-filter post-hoc.
    return {"keyword": query, "maxJobs": max(50, max_items), "fetchDetails": True}

def _glassdoor_input(query, max_items):
    # $0.03/item -> keep tiny. Drop sortBy (enum risk); date-filter via daysOld.
    return {"keywords": query, "location": INDIA_LOCATION,
            "daysOld": WINDOW_DAYS, "limit": max_items}

def _foundit_input(query, max_items):
    import urllib.parse as up
    q = up.quote(query.replace(" ", "-"))
    url = "https://www.foundit.in/srp/results?query=" + q + "&locations=India"
    return {"searchUrls": [url], "maxItems": max_items}

def _indeed_input(query, max_items):
    # Drop fromDays (enum "1"/"3"/"7"/"14") and sort (enum risk); filter post-hoc.
    return {"query": query, "country": "in", "location": INDIA_LOCATION,
            "maxRows": max_items}

def _hn_input(query, max_items):
    return {"mode": "hiring", "query": query, "maxItems": max_items}

ROSTER = [
    {
        "site": "LinkedIn Jobs",
        "actor": "curious_coder/linkedin-jobs-scraper",
        "build_input": _linkedin_input,
        "price_known": 0.001,
        "scope": "India (geo-filtered)",
        "queries": AI_QUERIES_LEAN,
        "scale_max_items": 50,     # per query  (~$0.001/item)
    },
    {
        "site": "Google Jobs",
        "actor": "johnvc/Google-Jobs-Scraper",
        "build_input": _google_input,
        "price_known": 0.0006,     # ~$0.006/10 measured
        "scope": "India (aggregates Indeed/LinkedIn/boards)",
        "queries": AI_QUERIES,
        "scale_max_items": 60,     # cheapest source -> widest net
    },
    {
        "site": "Naukri",
        "actor": "muhammetakkurtt/naukri-job-scraper",
        "build_input": _naukri_input,
        "price_known": None,       # calibrate
        "scope": "India",
        "queries": AI_QUERIES_LEAN,
        "scale_max_items": 50,
    },
    {
        "site": "Glassdoor",
        "actor": "valig/glassdoor-jobs-scraper",
        "build_input": _glassdoor_input,
        "price_known": 0.03,       # MEASURED $0.305/10 -> expensive, tiny sample
        "scope": "India",
        "queries": ["Data Scientist"],   # single query, small sample only
        "scale_max_items": 15,
    },
    {
        "site": "Foundit (Monster)",
        "actor": "easyapi/foundit-jobs-scraper",
        "build_input": _foundit_input,
        "price_known": 0.00299,    # + $0.09/run -> single broad run
        "run_fee": 0.09,
        "scope": "India",
        "queries": ["Artificial Intelligence"],   # 1 broad query (exact-match was too narrow)
        "scale_max_items": 40,
    },
    {
        "site": "Indeed",
        "actor": "borderline/indeed-scraper",
        "build_input": _indeed_input,
        "price_known": 0.005,
        "scope": "India (redundant w/ Google Jobs -> small cap)",
        "queries": AI_QUERIES_LEAN[:2],
        "scale_max_items": 25,
    },
    {
        "site": "HackerNews Who-is-Hiring",
        "actor": "agency-shift/hackernews-jobs-ask-scraper",
        "build_input": _hn_input,
        "price_known": 0.0,        # $0.05 flat start only
        "run_fee": 0.05,
        "scope": "GLOBAL (not India-specific - flagged)",
        "queries": ["AI"],
        "scale_max_items": 200,
    },
]

# Sites requested but NOT runnable -> reported as BLOCKED with reason.
BLOCKED_SITES = [
    {"site": "Kaggle Jobs", "reason": "Job board permanently closed (no live source / no actor)."},
    {"site": "Instahire",   "reason": "No dedicated Apify actor exists; only generic multi-source aggregators."},
    {"site": "LinkedIn (social/profiles)", "reason": "Out of scope: only LinkedIn *Jobs* scraped. Profile/people scraping omitted (ToS/compliance)."},
]
