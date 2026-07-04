# Deploy on Fly.io (monthly scheduled Machine)

The agent is a **batch job**: it boots, scrapes LinkedIn, writes BigQuery, and
exits. On Fly that's a **scheduled Machine** with `--schedule monthly` — no
always-on server, no `[http_service]`.

## Prereqs

- `flyctl` installed and logged in (`fly auth login`)
- The `market-research-bq@` service-account JSON key (see `IAM_REQUEST.md`)
- The Apify acct #2 (`hip_bouncer`) token

## 1. Create the app + image

```bash
cd "job_market_agent"
fly apps create ik-market-research-jobs        # or your chosen name (match fly.toml)
fly deploy --ha=false                          # builds image from Dockerfile, no machines kept running
```

> `fly deploy` builds and pushes the image. Because there's no `[http_service]`,
> you may see it start one machine that runs the job once and stops — that's
> harmless. The recurring run is the scheduled Machine below.

## 2. Set secrets (never in fly.toml or git)

```bash
# Apify token (read by harness.py from APIFY_TOKEN)
fly secrets set APIFY_TOKEN="<acct2_hip_bouncer_token>" -a ik-market-research-jobs

# BigQuery service-account key, base64-encoded (read by bigquery_writer.py)
#   macOS/Linux:
fly secrets set MARKET_RESEARCH_BQ_SA_B64="$(base64 -w0 market-research-bq.json)" -a ik-market-research-jobs
#   Windows PowerShell:
#   $b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\Users\Admin\.gcp-keys\market-research-bq.json"))
#   fly secrets set MARKET_RESEARCH_BQ_SA_B64="$b64" -a ik-market-research-jobs
```

Non-secret config (`JOBMKT_BQ_DATASET=Market_Research`, etc.) is already in
`fly.toml [env]`.

## 3. Register the monthly run

```bash
# Fly starts this Machine on the 1st of each month; it runs run_monthly.py and exits.
fly machine run . \
  --schedule monthly \
  --restart no \
  --region sin \
  -a ik-market-research-jobs
```

`--schedule` accepts `hourly | daily | weekly | monthly`. `--restart no` means
Fly won't restart it after the job exits 0 (it's a cron tick, not a service).

## 4. Verify

```bash
# One-off manual run (don't wait a month):
fly machine run . --restart no --region sin -a ik-market-research-jobs --command "python run_monthly.py"

# Logs of the latest run:
fly logs -a ik-market-research-jobs

# Confirm rows landed:
#   SELECT run_date, COUNT(*) FROM `ik-marketing-data.Market_Research.job_market_demand`
#   GROUP BY run_date ORDER BY run_date DESC;
```

## Notes for the Fly environment

- **Filesystem is ephemeral.** `output/` + `raw/` snapshots are written to the
  container and vanish when the Machine stops — that's fine, **BigQuery is the
  durable store**. (If you ever want the JSON snapshots persisted, mount a Fly
  volume or push them to GCS; not needed for the pipeline.)
- **Budget governor still applies.** It reads live Apify account spend over the
  API, so the $5-cap protection works identically on Fly.
- **Cost ~$0.70/run.** A monthly tick of a tiny Machine on Fly is negligible
  compute on top of that.
- The Windows files (`run_live.ps1`, `schedule_monthly.ps1`) are **local-only**
  and not shipped in the image (see `.dockerignore`). Use them only if you also
  want to run from your laptop.
