# Deploy on Fly.io (monthly Machine, started by the Cloudflare Worker)

The agent is a **batch job**: it boots, scrapes Naukri (`JOBMKT_SOURCE=naukri`),
writes BigQuery, and exits. On Fly that is **one stopped Machine** —
`7845393fe26338` in app `ik-market-research-jobs` — with no `[http_service]`.

> **Scheduler (rewritten 2026-10-27).** The Cloudflare Worker
> **`ik-ad-generator-trigger`** in **`christo0192/ik-mis` → `cloudflare-trigger/`**
> is the **ONLY** scheduler. It starts this Machine on the **1st of each month
> at 05:30 UTC (11:00 IST)**; the market-research pipeline follows on the 2nd so
> its Executive Summary reads the fresh jobs snapshot. (This repo's own
> `../cloudflare-trigger/` Worker is deployed without a cron and schedules
> nothing: Workers Free allows 5 crons per account and all are in use — see
> `../cloudflare-trigger/README.md`.) The Fly-native
> `--schedule monthly` that was registered on 2026-08-25 **never fired** (Aug,
> Sep and Oct 2026 were all missed) — **never set a Fly schedule on this
> Machine again**, or it can double-run alongside the Worker.

## Hard rules

- **Never run a plain `fly deploy` on this app.** The Machine is not a Fly Launch
  machine (`flyctl status`: "Found machines that aren't part of Fly Launch"), so
  `fly deploy` would **create a new Machine and start it** — an immediate live,
  paid Apify scrape — and the Worker would keep starting the old Machine ID.
  Always use **build-only + `fly machine update`** (§3).
- **Never `fly machine run . --schedule …`** and never pass `--schedule` to any
  update. The Worker is the scheduler.
- **Never `fly secrets deploy` on this app.** It only touches Fly Launch machines
  (there are none here). `fly machine update` (§3) is what makes the next boot
  use the current secrets.

## Prereqs

- `flyctl` installed and logged in (`fly auth login`)
- The `market-research-bq@` service-account JSON key (see `IAM_REQUEST.md`)
- The Apify acct #2 (`hip_bouncer`) token
- For the Worker token (§5): a checkout of `christo0192/ik-mis`, Node + `npm ci`
  in its `cloudflare-trigger/` folder, and Cloudflare auth (`npx wrangler login`
  once in a browser, or `CLOUDFLARE_API_TOKEN` with Workers Scripts:Edit on
  account `bbb3aa03755ccab33b6367bb6367294c`)

## 1. App + Machine (one-time — already done 2026-08-25)

Only needed if the app is ever rebuilt from scratch:

```bash
cd job_market_agent
fly apps create ik-market-research-jobs
fly deploy --build-only --push --image-label intel-init -a ik-market-research-jobs
# CREATE (not run) the Machine: stays stopped, no schedule, never restarted.
# fly.toml [env] does not apply to a non-Launch machine, so pass the source.
fly machine create registry.fly.io/ik-market-research-jobs:intel-init \
  --restart no --region sin --env JOBMKT_SOURCE=naukri -a ik-market-research-jobs
```

Then put the new Machine ID in the jobs-machine setting of the ik-mis Worker
(`christo0192/ik-mis` → `cloudflare-trigger/`, Worker `ik-ad-generator-trigger`)
and redeploy that Worker.

## 2. Secrets (never in fly.toml or git)

```bash
# Apify token (read by harness.py from APIFY_TOKEN)
fly secrets set APIFY_TOKEN="<acct2_hip_bouncer_token>" --stage -a ik-market-research-jobs

# BigQuery service-account key, base64-encoded (read by bigquery_writer.py)
#   macOS/Linux:
fly secrets set MARKET_RESEARCH_BQ_SA_B64="$(base64 -w0 market-research-bq.json)" --stage -a ik-market-research-jobs
#   Windows PowerShell:
#   $b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\Users\Admin\.gcp-keys\market-research-bq.json"))
#   fly secrets set MARKET_RESEARCH_BQ_SA_B64="$b64" --stage -a ik-market-research-jobs
```

`fly secrets list` shows these as **Staged** on this app forever — the label is a
timestamp comparison against a Fly Launch release, which this Machine has none
of. It does not mean the secret is missing. The proof is the `--preflight` smoke
in §4, run after the `machine update` in §3.

Non-secret config defaults in `config.py` match `fly.toml [env]`; the only env
on the Machine itself is `JOBMKT_SOURCE=naukri`.

## 3. Ship a new image (the normal "deploy")

```bash
cd job_market_agent
TAG=intel-monthly-$(git rev-parse --short HEAD)
# Build + push ONLY — creates/starts nothing.
fly deploy --build-only --push --image-label "$TAG" -a ik-market-research-jobs

# Point the existing Machine at it. It stays stopped (--skip-start), keeps
# restart=no, and the next boot picks up the current secrets. The JSON file
# clears any Fly schedule (an empty --schedule flag is ignored by flyctl).
printf '{"schedule":""}' > "$TEMP/noschedule.json"   # path must end in .json
fly machine update 7845393fe26338 -a ik-market-research-jobs \
  --image "registry.fly.io/ik-market-research-jobs:$TAG" \
  --machine-config "$TEMP/noschedule.json" --restart no --skip-start -y
```

(PowerShell 5.1 strips the quotes from inline JSON, which is why the schedule
reset goes through a `.json` file.)

## 4. Preflight smoke (no spend)

`run_monthly.py --preflight` checks that `APIFY_TOKEN` and the BigQuery SA are
present, runs one BigQuery `SELECT 1`, prints `preflight OK` and exits 0. It never
calls Apify and never writes BigQuery. Run it in a throwaway Machine:

```bash
fly machine run "registry.fly.io/ik-market-research-jobs:$TAG" --rm --restart no \
  --region sin --env JOBMKT_SOURCE=naukri -a ik-market-research-jobs \
  -- python run_monthly.py --preflight
fly logs -a ik-market-research-jobs
# expect: [preflight] BigQuery OK ... / preflight OK

# The real Machine must show no schedule, restart no, state stopped:
fly machines list -a ik-market-research-jobs --json
```

The command goes **positionally, after `--`**. Never use `--command "…"` here:
`fly machine run` reads `--command` only together with `--shell` and otherwise
silently boots the image CMD — the full LIVE paid Naukri scrape plus a BigQuery
DELETE + append of the month (flyctl v0.4.110, `internal/command/machine/run.go`).
If the logs show `=== Job Market Demand agent` at any point (the live-run banner;
`--preflight` never prints it), the override did not apply: kill that Machine at
once with
`fly machine destroy --force <id printed by machine run> -a ik-market-research-jobs`.

Exit codes of `run_monthly.py` (what the Machine's exit shows after a run):

| code | meaning |
|---|---|
| 0 | OK (or `--preflight` passed) |
| 2 | preflight failed — a secret / BQ credential is missing, or BQ auth (`SELECT 1`) or the target-table check failed. Checked **before** the Apify scrape on every run, so nothing was spent |
| 3 | live run produced 0 rows (every query failed or was budget-skipped) |
| 4 | **partial** live run: fewer than 80% (`MIN_QUERY_SUCCESS_SHARE`) of the planned queries returned data — `[ERR]`, `[LAUNCH-ERR]`, `[RUN-ERR]` (actor run FAILED / ABORTED / TIMED-OUT with 0 items), `[GUARD-SKIP]`, or queries never run after an `[ABORT]`. BigQuery was **not** written, so the month keeps its previous snapshot; fix the cause and re-run (§6) |
| 5 | **degraded** live run: some queries failed but coverage passed the 80% gate; the snapshot **was** written without them (`output/run_manifest.json` → `fetch.queries_failed`) |
| 1 | uncaught error (traceback in `fly logs`) |

## 5. The scheduler: Cloudflare Worker `ik-ad-generator-trigger` (ik-mis)

Lives in **`christo0192/ik-mis` → `cloudflare-trigger/`**, not in this repo. Its
one cron, `30 5 * * *` (05:30 UTC = 11:00 IST, daily), starts the
`ik-ad-generator` Machine every day and also dispatches on the UTC day of the
month: **day 1 starts this Machine**, day 2 starts the market-research
pipeline, any other day starts neither. The generator start does not depend on
these two starts and is never blocked or delayed by them. The handler only POSTs
the Fly Machines API `start` and never throws (a Cloudflare retry would
double-start a paid run).

This repo's own `../cloudflare-trigger/` Worker (same day-1/day-2 dispatch on
its own cron) is deployed **without a cron**: Cloudflare refused it because
Workers Free allows 5 cron triggers per account and all 5 are in use. Its code
and tests stay for a possible move to Workers Paid; `../cloudflare-trigger/README.md`
explains the status. Never give it a cron while the ik-mis Worker dispatches
this Machine, or every month is scraped (and paid for) twice.

Timing: 05:30 UTC keeps the UTC and IST dates equal, so "day 1" is the 1st in
both. The pipeline starts 24 h after this Machine, so its Executive Summary
still reads this month's jobs snapshot. On the 1st, the Generation run that the
same cron starts reads `Market_Research` while this Machine is still scraping,
so that day's generation can still see the previous month's jobs snapshot.

The Worker authenticates with an **app-scoped Fly deploy token** (least privilege:
it can manage only this app). Create it and pipe it straight into the ik-mis
Worker secret so it is never echoed or saved:

```bash
cd <ik-mis checkout>/cloudflare-trigger    # Worker ik-ad-generator-trigger
npm ci
fly tokens create deploy -a ik-market-research-jobs -n ik-ad-generator-trigger -x 26280h \
  | npx wrangler secret put FLY_TOKEN_JOBS
```

`wrangler secret put` updates the deployed Worker directly. Deploy the Worker
itself from ik-mis (per its own docs); `npx wrangler deploy` output must list
the schedule `"30 5 * * *"`.

`-x 26280h` = 3 years. **Record the creation date** when you mint it (expiry =
creation + 3 years); an expired token makes the 1st-of-month start fail with a
401 that only shows up in the Worker logs. Deploy tokens print as `FlyV1 fm2_…`;
the Worker sends this one as-is (`Authorization: FlyV1 fm2_…`, as flyctl does).
Fly also accepts `Bearer FlyV1 fm2_…`, which is what the generator start has
always sent with its own deploy token `FLY_TOKEN`: leave that header alone. A
401 here points at the token (expired, revoked, other app), not the header.

Check a fired run on the 1st: `npx wrangler tail ik-ad-generator-trigger` (or
Workers observability logs for `ik-ad-generator-trigger`) shows the jobs start
returning 200, next to the usual generator start.

## 6. Ad-hoc refresh (don't wait for the 1st)

Starting the real Machine runs the full LIVE job (~$0.70 of Apify):

```bash
fly machine start 7845393fe26338 -a ik-market-research-jobs
fly logs -a ik-market-research-jobs
fly machine status 7845393fe26338 -a ik-market-research-jobs   # wait for stopped + exit_code 0
```

If you also refresh the market-research pipeline, start it only **after** this
Machine has stopped with exit 0 (its Executive Summary reads the latest jobs
snapshot) — see `../market_research/DEPLOY_FLY.md` §6.

Do **not** use `fly machine run . …` for a refresh: that builds and creates new
Machines.

## 7. Verify + run_id semantics

```sql
SELECT run_id, run_date, COUNT(*) n
FROM `ik-marketing-data.Market_Research.job_market_demand`
GROUP BY run_id, run_date ORDER BY run_date DESC;
```

- `run_id = <source>-<YYYY-MM>` of the **run** date (container clock is UTC). The
  run on 2026-11-01 writes `naukri-2026-11` with a rolling 32-day window
  (2026-09-30 .. 2026-11-01), i.e. mostly October postings. The label is the run
  month, kept for continuity with `naukri-2026-08` / `linkedin-2026-06`.
- A rerun in the **same month** first `DELETE`s that run_id, then appends —
  one snapshot per month. A rerun that slips into the next month makes a new
  snapshot (intended). Consumers read `MAX(run_date)`.
- DELETE-then-append is not atomic: a crash between the two leaves the month
  empty until a rerun.

## Notes for the Fly environment

- **Filesystem is ephemeral.** `output/` + `raw/` snapshots are written to the
  container and vanish when the Machine stops — that's fine, **BigQuery is the
  durable store**.
- **Budget governor still applies.** It reads live Apify account spend over the
  API, so the $5-cap protection works identically on Fly.
- **Cost ~$0.70/run.** A monthly tick of a tiny Machine on Fly is negligible
  compute on top of that.
- The Windows files (`run_live.ps1`, `schedule_monthly.ps1`) are **local-only**
  and not shipped in the image (see `.dockerignore`). Don't run them alongside
  the Worker, or a month gets scraped (and paid for) twice.
