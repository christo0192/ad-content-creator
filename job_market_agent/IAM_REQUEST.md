> ✅ **FULFILLED 2026-06-25.** Dataset `Market_Research` (US) created; SA
> `market-research-bq@ik-marketing-data` provisioned with `jobUser` +
> `dataEditor` (least-privilege verified). Key in Secret Manager as
> `sa-key-market-research-bq`; pulled to `C:\Users\Admin\.gcp-keys\market-research-bq.json`.
> Both pipelines flipped to the production dataset and all 5 tables verified live.
> The request below is kept as the record of what was asked.

# Request: new dataset + service account — Market Research Agent

**Project:** `ik-marketing-data`
**Requested by:** india.sales@interviewkickstart.com
**Workload:** Market-research agent pipeline (AI/ML India). First table live: monthly LinkedIn **job-market demand**. The same dataset will later hold the other tabs (social trends, blog/publications, competitor intel, executive summary) + back a frontend dashboard.

This follows the per-workload least-privilege pattern in
`Call Analysis Intelligence (CAI)/docs/SERVICE_ACCOUNT_AUDIT.md`.

---

## 1. Create one dataset

| | Value |
|---|---|
| Dataset ID | `Market_Research` |
| Project | `ik-marketing-data` |
| Location | **US** (match existing datasets) |

> Pre-create it so the SA never needs project-level `datasets.create`. The
> pipeline uses `create_table(exists_ok=True)`, so it won't try to make the
> dataset itself.

## 2. Create one service account

| | Value |
|---|---|
| Name | `market-research-bq` |
| Email | `market-research-bq@ik-marketing-data.iam.gserviceaccount.com` |
| Used by | the monthly scraper on Christo's machine (and future tabs of the same project) |

## 3. Grant exactly these roles (least privilege)

| Scope | Role | Why |
|---|---|---|
| Project `ik-marketing-data` | `roles/bigquery.jobUser` | run load / query / delete jobs |
| Dataset `Market_Research` | `roles/bigquery.dataEditor` | create tables, append snapshots, idempotent `DELETE WHERE run_id=…`, read-back |

**OAuth scopes** (set in code): `bigquery`, `cloud-platform`. **No Drive scope**
(no Sheets-federated tables).

## 4. What it does NOT need (please don't grant)

- ❌ `roles/bigquery.admin` — too broad
- ❌ any read/write on `India_Leads`, `Marketing_data_new_logic`, or other
  upstream datasets — this pipeline reads **only** from Apify, never from BQ
- ❌ `datasets.create` / `datasets.delete` / `setIamPolicy` — dataset is
  pre-created; never mutates IAM
- ❌ `routines.create`, `connections.create`

This SA is strictly write-scoped to one dataset + job execution. Total
compromise leaks only public job-posting aggregates (no PII).

## 5. Key delivery

Issue a JSON key and hand it to Christo. **This workload runs on Fly.io**, so the
key is consumed as a **Fly secret** (base64-encoded), not a file on a server:

```bash
fly secrets set MARKET_RESEARCH_BQ_SA_B64="$(base64 -w0 market-research-bq.json)" \
  -a ik-market-research-jobs
```

(A copy may also sit at `C:\Users\Admin\.gcp-keys\market-research-bq.json` for
local runs, same convention as the other 6 SAs.) 90-day rotation, standard
key handling — never commit it.

## 6. One-shot commands (if the team prefers CLI)

```bash
# dataset
bq --location=US mk --dataset ik-marketing-data:Market_Research

# service account
gcloud iam service-accounts create market-research-bq \
  --project=ik-marketing-data \
  --display-name="Market Research Agent (BQ writer)"

# project: jobUser
gcloud projects add-iam-policy-binding ik-marketing-data \
  --member="serviceAccount:market-research-bq@ik-marketing-data.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

# dataset: dataEditor — easiest in console:
#   BigQuery → Market_Research → Sharing → Permissions →
#   Add principal: market-research-bq@ik-marketing-data.iam.gserviceaccount.com
#   Role: BigQuery Data Editor

# key
gcloud iam service-accounts keys create market-research-bq.json \
  --iam-account=market-research-bq@ik-marketing-data.iam.gserviceaccount.com
```

## 7. Smoke test (proves the grant is correct)

```python
from google.cloud import bigquery
from google.oauth2 import service_account
creds = service_account.Credentials.from_service_account_file(
    r"C:\Users\Admin\.gcp-keys\market-research-bq.json",
    scopes=["https://www.googleapis.com/auth/bigquery",
            "https://www.googleapis.com/auth/cloud-platform"])
c = bigquery.Client(credentials=creds, project="ik-marketing-data")
c.query("CREATE TABLE IF NOT EXISTS `ik-marketing-data.Market_Research._smoke_DELETE_ME`(x INT64)").result()
c.query("INSERT INTO `ik-marketing-data.Market_Research._smoke_DELETE_ME`(x) VALUES(1)").result()
c.query("DROP TABLE `ik-marketing-data.Market_Research._smoke_DELETE_ME`").result()
print("OK — dataEditor + jobUser confirmed")
```

Expect all three to succeed. A `PERMISSION_DENIED` means a grant is missing —
escalate before closing.

---

## After the key is delivered

Going live on the real dataset is two env vars (no code change):

```powershell
$env:JOBMKT_BQ_KEY     = "C:\Users\Admin\.gcp-keys\market-research-bq.json"
$env:JOBMKT_BQ_DATASET = "Market_Research"
```

## Addendum — read-only SA for the dashboard (REQUESTED 2026-06-26)

The dashboard is built and deploying to Vercel (private repo
`christo0192/ik-market-research-dashboard`). Please provision a **dedicated
read-only** identity so the web app's key can never mutate BigQuery (the app
currently runs on the `market-research-bq` writer key as an interim measure):

| | Value |
|---|---|
| Name | `market-research-dash-bq` |
| Email | `market-research-dash-bq@ik-marketing-data.iam.gserviceaccount.com` |
| Project `ik-marketing-data` | `roles/bigquery.jobUser` |
| Dataset `Market_Research` | `roles/bigquery.dataViewer` (read-only — NO dataEditor) |

**Key delivery:** same Secret Manager convention as the writer SA — store the
JSON key as secret **`sa-key-market-research-dash-bq`** and grant Christo
`secretAccessor` on it. He fetches with:

```bash
gcloud secrets versions access latest --secret=sa-key-market-research-dash-bq \
  --project=ik-marketing-data > market-research-dash-bq.json
```

Then it's base64'd into the Vercel env var `MARKET_RESEARCH_BQ_SA_B64` — no code
change (the loader is identical to the writer path).

What it must NOT have: any `dataEditor`/write role, `datasets.create`, access to
other datasets. Read-only on `Market_Research` + jobUser is the whole footprint.

```bash
gcloud iam service-accounts create market-research-dash-bq --project=ik-marketing-data \
  --display-name="Market Research Dashboard (BQ read-only)"
gcloud projects add-iam-policy-binding ik-marketing-data \
  --member="serviceAccount:market-research-dash-bq@ik-marketing-data.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"
# + grant BigQuery Data Viewer on the Market_Research dataset (console or bq).
```
