# Market Research Agent — weekly pipeline (Tabs 1, 2, 4 + Executive Summary)

Reproduces the "CK's AI/ML Market Research India" workbook. This package is the
**weekly** half (Social Trends, Blog & Publications, Competitor Intelligence,
Executive Summary). The **monthly** Job-Market tab (Tab 3, LinkedIn) is the
sibling `../job_market_agent`.

```
            ┌──────────────── run_weekly.py (orchestrator) ───────────────┐
            │  dispatch → validate (Pydantic gate) → BigQuery per tab       │
            ▼                     ▼                      ▼                   │
   agent_social.py        agent_blog.py          agent_competitor.py        │
   GitHub/HN/PyPI/npm     arXiv+RSS → Haiku       Jina Reader → Haiku        │
   (+Reddit if Apify)     extract                 extract (14-col)           │
            └──────────────────────────┬──────────────────────────────────┘
                                       ▼
                          exec_summary.py (Sonnet)
              ranked priorities over all 4 tabs (Jobs read from BQ)
```

**LLM = `claude -p` (Claude Code headless, Max plan) — no API key.** Haiku for
extraction, Sonnet 4.6 for the Executive Summary. Output is fence-stripped,
JSON-parsed, and validated against the per-tab Pydantic schema before any BQ write.

## Layout

| Path | Role |
|---|---|
| `shared/config.py` | BQ target, models, cadence window, Apify ceilings |
| `shared/schemas.py` | Pydantic models + BQ schemas for all tabs (the tool-call gate) |
| `shared/llm.py` | `claude -p` wrapper: `extract_json` / `synthesize` / `map_extract` |
| `shared/bq.py` | generic partitioned-snapshot writer (env-creds; local + Fly) |
| `shared/fetch.py` | http/json, RSS, Jina Reader, trafilatura |
| `shared/governor.py` | Apify budget governor (Reddit only) |
| `agents/agent_social.py` | Tab 1 — Social Trends (free, no LLM) |
| `agents/agent_blog.py` | Tab 2 — Blog & Publications (Haiku extract) |
| `agents/agent_competitor.py` | Tab 4 — Competitor Intelligence (Haiku extract) |
| `exec_summary.py` | Executive Summary synthesis (Sonnet) |
| `run_weekly.py` | orchestrator entrypoint |

## Run

```powershell
pip install -r requirements.txt          # feedparser, trafilatura, bigquery, pydantic, requests
# claude CLI must be installed + logged in (Max plan) for LLM steps

python run_weekly.py                      # full run -> BigQuery
python run_weekly.py --only social        # one agent (social is fully free, no LLM)
python run_weekly.py --no-bq              # collect + synthesize, skip BQ
python run_weekly.py --no-exec            # skip Executive Summary
```

`agent_social.py` runs with zero LLM and zero spend — the fastest smoke test.

## BigQuery tables (one per tab, partitioned by `run_date`)

`{project}.{dataset}.` → `social_trends`, `blog_publications`, `competitor_intel`,
`executive_summary` (+ `job_market_demand` from the monthly agent).
Dataset defaults to **`cai_dev_sandbox`** (interim) → set `MR_BQ_DATASET=Market_Research`
once provisioned (see `../job_market_agent/IAM_REQUEST.md`).

## Config knobs (env)

| Var | Default | Use |
|---|---|---|
| `MR_BQ_DATASET` | `cai_dev_sandbox` | flip to `Market_Research` |
| `MR_EXTRACT_MODEL` / `MR_SYNTH_MODEL` | `haiku` / `sonnet` | model selection for `claude -p` |
| `MR_WEEKLY_WINDOW_DAYS` | `7` | recency window |
| `MR_CADENCE` | `weekly` | `monthly` → run_id `monthly-YYYY-MM` (one snapshot per month; set on Fly) |
| `MR_RUN_ID` | — | force an explicit run_id (backfills) |
| `MR_REQUIRE_LLM_TOKEN` | — | `1` → preflight demands `CLAUDE_CODE_OAUTH_TOKEN`/`ANTHROPIC_API_KEY` off Fly too |
| `MR_BLOG_MAX` | `18` | max articles extracted/run (LLM cost/latency cap) |
| `MR_LLM_CONCURRENCY` | `4` | parallel `claude -p` calls (respect Max-plan limits) |
| `APIFY_TOKEN` | — | optional; enables Reddit in Social |

## Source coverage (vs reference workbook)

**Social:** GitHub ✅, version signals (PyPI/npm) ✅, **Reddit** ✅ (needs `APIFY_TOKEN`,
free acct #2). **Twitter/X** intentionally dropped — no free API since Feb 2026 (paid-only).

**Blog (8/10 covered):** RSS — Towards Data Science, DataAspirant, Entrepreneur India,
arXiv. Scrape (Jina listing) — Analytics India Magazine, AIM Research, Tredence,
KodeKloud. **Not covered:** TechGig + LiquidMetal AI return near-empty via Jina
(JS/anti-scrape walls) — genuine limitation; would need a headless browser
(Playwright) or paid scraper.

**Competitor:** Scaler, Great Learning, UpGrad, Udacity, Emeritus, Simplilearn
(thin-page trafilatura fallback). Form-gated prices stay null + `confidence: low`.

Low-frequency RSS sources fall back to most-recent posts when nothing is in the
weekly window, so every source is still represented each run.

## Notes

- **Latency:** each `claude -p` call is a full CLI process (~25–45s cold start).
  A full weekly run is a few minutes — fine for batch. Tune `MR_BLOG_MAX` /
  `MR_LLM_CONCURRENCY` to trade breadth vs time.
- **Sentiment** in Social is a transparent magnitude heuristic (trending tech
  skews positive); swap to a `claude -p` sentiment pass if you want nuance.
- **Competitor pricing** is often form-gated → `price_inr` null + `confidence:low`
  is the honest result, not a bug.
- Deploy: see **`DEPLOY_FLY.md`** — one stopped Fly Machine started **monthly**
  (2nd, 03:30 UTC) by the Cloudflare Worker `ik-intelligence-trigger`
  (`../cloudflare-trigger/`); no Fly-native schedule. On Fly `MR_CADENCE=monthly`
  gives run_id `monthly-YYYY-MM`. Smoke: `python run_weekly.py --preflight`.
