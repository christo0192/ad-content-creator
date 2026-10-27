# Job Market Demand Agent — LinkedIn (monthly)

Agent 3 ("Job Market Demand", Tab 3) of the IK India AI/ML market-research
workbook. **Scope lock (2026-06-23):** LinkedIn **only**, run **once a month**,
store to **BigQuery**. Naukri / Foundit / Glassdoor / Google Jobs are
intentionally not used here. The other three market-research agents keep their
own plans — this package is self-contained.

## What it does (per run)

```
LinkedIn (Apify curious_coder/linkedin-jobs-scraper, India, last 32d)
  -> normalize         (linkedin native fields)
  -> AI-classify       (taxonomy filter: drop non-AI/ML titles + company tier)
  -> score             (emerging-role bucket + skills/tools from description)
  -> Pydantic validate (JobDemandRow = the tool-call gate)
  -> dedup             (by LinkedIn job id)
  -> BigQuery          (monthly snapshot, partitioned by run_date)
  +  local snapshot    (output/job_demand_rows.json + run_manifest.json)
```

Demand trends (MoM / YoY) are a **query over the partitioned table**, not a
per-row guess — each monthly run is one `run_date` snapshot.

## Layout

| File | Role |
|---|---|
| `config.py` | scope: queries, India geoId, monthly window, budget ceilings, BQ target |
| `harness.py` | Apify **budget governor** + governed actor runner (reads real account spend, hard-aborts under the $5 cap) |
| `normalize.py` | LinkedIn raw item -> unified row |
| `classify.py` | AI-role taxonomy filter, India company-tier rubric, date/salary parse |
| `scoring.py` | emerging-role buckets + skills/tools extraction |
| `schema.py` | `JobDemandRow` Pydantic model + BigQuery schema (kept in lockstep) |
| `bigquery_writer.py` | ensure table, idempotent monthly snapshot load |
| `run_monthly.py` | orchestrator (live + `--dry-run`) |
| `run_live.ps1` / `schedule_monthly.ps1` | monthly Windows scheduling |

## Setup

```powershell
pip install -r requirements.txt
```

**BigQuery auth** — service-account creds, resolved in this order (works local
*and* on Fly):
1. `MARKET_RESEARCH_BQ_SA_B64` (base64 SA JSON — the **Fly secret**)
2. `MARKET_RESEARCH_BQ_SA_JSON` (inline JSON or a file path)
3. `JOBMKT_BQ_KEY` / `config.BQ_SA_KEY` (local key file; defaults to the dev SA
   `C:\Users\Admin\.gcp-keys\claude-code-dev-bq.json`)
4. Application Default Credentials

**Apify token (live only)** — Apify acct #2 `hip_bouncer` (FREE $5/mo cap), read
from `APIFY_TOKEN`. On Fly: `fly secrets set APIFY_TOKEN=…`. Locally: set
`$env:APIFY_TOKEN`, or put the raw token one-line in
`C:\Users\Admin\.secrets\apify_acct2.token` (used by `run_live.ps1`).

## Run

```powershell
# Verify the full pipeline with NO Apify spend (reuses existing raw LinkedIn JSON,
# still writes to BigQuery):
python run_monthly.py --dry-run

# Process + validate only, skip BQ:
python run_monthly.py --dry-run --no-bq

# LIVE monthly run (needs APIFY_TOKEN):
$env:APIFY_TOKEN = (Get-Content C:\Users\Admin\.secrets\apify_acct2.token -Raw).Trim()
python run_monthly.py
```

## Schedule (monthly)

**Production target = Fly.io** (one stopped batch Machine). Since 2026-10-27 the
**only** scheduler is the Cloudflare Worker `ik-intelligence-trigger`
(`../cloudflare-trigger/`), which starts the Machine on the 1st at 03:30 UTC
(09:00 IST). The old Fly `--schedule monthly` never fired — never set it again,
and never run a plain `fly deploy` on this app (it creates + starts a new
Machine = a live paid scrape). See **`DEPLOY_FLY.md`** for the build-only +
`fly machine update` flow, secrets, and the no-spend smoke:

```bash
python run_monthly.py --preflight   # secrets + BQ SELECT 1; exit 0 = OK, 2 = missing
```

On Fly the filesystem is ephemeral — **BigQuery is the durable store**; the
`output/`+`raw/` JSON snapshots are just local convenience.

**Local Windows scheduling (optional, legacy)** — only if you run from your
laptop *instead of* Fly; running both scrapes (and pays for) the month twice.
Not shipped in the Fly image (`.dockerignore`):

```powershell
powershell -ExecutionPolicy Bypass -File schedule_monthly.ps1   # 2nd of month, 09:00
powershell -ExecutionPolicy Bypass -File schedule_monthly.ps1 -Remove
```

## Cost

LinkedIn actor ≈ **$0.001/row** (measured). 14 queries × 50 rows ≈ 700 rows ≈
**~$0.70/run**, i.e. ~$0.70/month — comfortably inside the acct #2 $5 FREE cap.
The budget governor refuses to launch a query if it could cross the hard ceiling
(`SESSION_HARD_ABORT_USD = $2.00`), so a single run can never drain the account
(the lesson from the 2026-06 Google-Jobs overshoot).

## BigQuery target

| | value |
|---|---|
| Project | `ik-marketing-data` |
| Dataset | `cai_dev_sandbox` *(interim — see below)* |
| Table | `job_market_demand` |
| Partition | `run_date` (monthly) |
| Cluster | `normalized_role`, `company_tier` |

### ⚠️ Production dataset — IAM ask

The data table currently lands in **`cai_dev_sandbox`** because the dev SA
(`claude-code-dev-bq@`) has `dataEditor` there but **cannot create a new
top-level dataset**. For the permanent home + the dashboard, ask the data team to:

1. **Create dataset** `ik-marketing-data.Market_Research` (US).
2. Grant the run identity `roles/bigquery.dataEditor` on it. Either:
   - reuse `claude-code-dev-bq@` (dev/interactive), **or**
   - provision a dedicated `market-research-bq@` SA (recommended for the
     unattended monthly job — mirrors the per-workload SA pattern in
     `Call Analysis Intelligence (CAI)/docs/SERVICE_ACCOUNT_AUDIT.md`).

Then flip one env var — no code change:
```powershell
$env:JOBMKT_BQ_DATASET = "Market_Research"
# and JOBMKT_BQ_KEY if a dedicated SA is issued
```

## Sample query (dashboard backing)

```sql
-- AI/ML hiring demand by role, this month
SELECT normalized_role, role_family,
       COUNT(*) AS postings,
       COUNTIF(is_emerging) AS emerging_postings,
       APPROX_TOP_COUNT(company, 5) AS top_companies
FROM `ik-marketing-data.cai_dev_sandbox.job_market_demand`
WHERE run_date = (SELECT MAX(run_date) FROM `ik-marketing-data.cai_dev_sandbox.job_market_demand`)
  AND in_window
GROUP BY normalized_role, role_family
ORDER BY postings DESC;
```
