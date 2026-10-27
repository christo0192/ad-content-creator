# Deploy on Fly.io (monthly Machine, started by the Cloudflare Worker)

Batch job: boots, runs the 3 collector agents (Social, Blog, Competitor) + the
Executive Summary, writes BigQuery, exits. The image bundles **Python + the
Claude Code CLI** because all LLM calls go through `claude -p`. On Fly it is **one
stopped Machine** — `7812565f9d3378` in app `ik-market-research-weekly` (the
"weekly" names are historical; it runs monthly).

> **Scheduler (rewritten 2026-10-27).** The Cloudflare Worker
> **`ik-intelligence-trigger`** (`../cloudflare-trigger/`) is the **ONLY**
> scheduler. It starts this Machine on the **2nd of each month at 03:30 UTC
> (09:00 IST)** — the day after the jobs agent (`../job_market_agent`, 1st), so
> the Executive Summary reads the fresh `job_market_demand` snapshot. The
> Fly-native `--schedule` registered on 2026-08-25 **never fired** (Aug, Sep and
> Oct 2026 were all missed) — **never set a Fly schedule on this Machine again**,
> or it can double-run alongside the Worker.

## Prereqs

- `flyctl` installed + logged in
- `market-research-bq@` service-account key (see `../job_market_agent/IAM_REQUEST.md`)
- A **Claude Code OAuth token** for headless auth on the Max plan:
  ```bash
  claude setup-token        # run locally in a normal terminal; prints a long-lived token
  ```
- (optional) Apify acct #2 token if you want Reddit in the Social tab
- For the Worker (§5): Node + `npm ci` in `../cloudflare-trigger`, and Cloudflare
  auth (`npx wrangler login` once in a browser, or `CLOUDFLARE_API_TOKEN` with
  Workers Scripts:Edit on account `bbb3aa03755ccab33b6367bb6367294c`)

## 1. App + Machine (one-time — already done 2026-08-25)

```bash
cd market_research
fly apps create ik-market-research-weekly      # match fly.toml
fly deploy --ha=false                          # creates the one Fly Launch Machine
```

Unlike the jobs app, this Machine **is** a Fly Launch machine, so `fly deploy`
updates it in place. If it is ever recreated, put the new ID in
`../cloudflare-trigger/wrangler.toml` (`WEEKLY_MACHINE_ID`) and redeploy the Worker.

## 2. Secrets

```bash
# Claude Code Max-plan auth (so `claude -p` works headless in the container)
fly secrets set CLAUDE_CODE_OAUTH_TOKEN="<from claude setup-token>" --stage -a ik-market-research-weekly

# BigQuery writer SA (base64 of the JSON key)
fly secrets set MARKET_RESEARCH_BQ_SA_B64="$(base64 -w0 market-research-bq.json)" --stage -a ik-market-research-weekly

# optional: Reddit
fly secrets set APIFY_TOKEN="<acct2 token>" --stage -a ik-market-research-weekly

# push staged secrets to the (stopped) Machine without starting it
fly secrets deploy -a ik-market-research-weekly
```

(`ANTHROPIC_API_KEY` works instead of `CLAUDE_CODE_OAUTH_TOKEN`; the `claude` CLI
reads either.) Non-secret config (`MR_BQ_DATASET=Market_Research`, model names,
`MR_CADENCE=monthly`, `MR_WEEKLY_WINDOW_DAYS=32`) is in `fly.toml [env]`.

## 3. Ship a new image

```bash
cd market_research
fly deploy --ha=false -a ik-market-research-weekly
```

This updates the existing stopped Machine `7812565f9d3378` and **leaves it
stopped**; it also applies `fly.toml [env]` and `[[restart]] policy = "never"`
(without that block `fly deploy` would reset restart=no). `fly deploy` clones the
old Machine config, so a lingering Fly schedule would survive it — clear it
afterwards (an empty `--schedule` flag is ignored by flyctl, hence the file):

```bash
printf '{"schedule":""}' > "$TEMP/noschedule.json"   # path must end in .json
fly machine update 7812565f9d3378 -a ik-market-research-weekly \
  --machine-config "$TEMP/noschedule.json" --restart no --skip-start -y
```

The CLI is pinned in the `Dockerfile` (`CLAUDE_CODE_VERSION`, on Node 24). Bump
it deliberately and re-run §4 after the rebuild.

## 4. Preflight smoke (no collection, no writes)

`run_weekly.py --preflight` checks the BigQuery SA and (on Fly) the LLM token,
runs one BigQuery `SELECT 1` and one tiny `claude -p` call per LLM tier
(extraction `MR_EXTRACT_MODEL`/`MR_EXTRACT_EFFORT`, synthesis
`MR_SYNTH_MODEL`/`MR_SYNTH_EFFORT` — exactly as the run calls them), prints
`preflight OK` and exits 0. Run it in a throwaway Machine on the new image:

```bash
fly image show -a ik-market-research-weekly           # note the deployment tag
fly machine run "registry.fly.io/ik-market-research-weekly:<deployment tag>" --rm --restart no \
  --region sin --vm-cpus 2 --vm-memory 4096 -a ik-market-research-weekly \
  --env MR_CADENCE=monthly --env MR_WEEKLY_WINDOW_DAYS=32 \
  -- python run_weekly.py --preflight
fly logs -a ik-market-research-weekly
# expect: [preflight] BigQuery OK ... / [preflight] claude -p OK (extract ...) /
#         [preflight] claude -p OK (synth ...) / preflight OK

# The real Machine must show no schedule, restart no, state stopped:
fly machines list -a ik-market-research-weekly --json
```

- The command goes **positionally, after `--`**. Never use `--command "…"`:
  `fly machine run` reads `--command` only together with `--shell` and otherwise
  silently boots the image CMD — the whole pipeline: every `claude -p` call, the
  Reddit Apify scrape and a DELETE + append on all four tables (flyctl v0.4.110,
  `internal/command/machine/run.go`). If the logs show `=== Market Research` at
  any point (the live-run banner; `--preflight` never prints it), the override
  did not apply: kill that Machine at once with
  `fly machine destroy --force <id printed by machine run> -a ik-market-research-weekly`.
- `fly machine run` does **not** apply `fly.toml [env]` (only `--env`). The two
  `--env` flags are the `[env]` values that differ from the `config.py` defaults,
  so the throwaway Machine sees the same config as the real one (a test guards
  that every other `[env]` value equals its default).

Exit codes of `run_weekly.py` (what the Machine's exit shows after a run):

| code | meaning |
|---|---|
| 0 | every tab that ran produced rows, plus the Executive Summary on a full run |
| 1 | degraded — a tab errored or produced 0 rows (e.g. the Claude token expired, so blog/competitor/exec are empty), or an uncaught error |
| 2 | preflight failed — missing BQ creds / LLM token, or the `--preflight` probe (BQ or either LLM tier) failed. Nothing was collected or written |

## 5. The scheduler: Cloudflare Worker `ik-intelligence-trigger`

Lives in `../cloudflare-trigger/`. One cron, `30 3 1,2 * *` (03:30 UTC = 09:00
IST); the handler dispatches on the UTC day: day 1 starts the jobs Machine, **day
2 starts this Machine**, any other day does nothing. It only POSTs the Fly
Machines API `start`; it never throws (a Cloudflare retry would double-start).
A transient failure (5xx / 429 / network / 15 s timeout) is retried in-handler up
to 3 attempts within ~1 min; any other 4xx (e.g. a 401 expired token) is final.

The Worker authenticates with an **app-scoped Fly deploy token** (least
privilege). Create it and pipe it straight into the Worker secret so it is never
echoed or saved:

```bash
cd ../cloudflare-trigger
npm ci
fly tokens create deploy -a ik-market-research-weekly -n ik-intelligence-trigger -x 26280h \
  | npx wrangler secret put FLY_TOKEN_WEEKLY
npx wrangler deploy        # output must list the schedule "30 3 1,2 * *"
```

`-x 26280h` = 3 years. **Record the creation date** when you mint it (expiry =
creation + 3 years); an expired token makes the 2nd-of-month start fail with a
401 that only shows up in the Worker logs. Check a fired run with
`npx wrangler tail ik-intelligence-trigger` (`weekly start OK (200)`).

## 6. Ad-hoc refresh (don't wait for the 2nd)

Run the jobs agent first and wait for it to stop with exit 0
(`../job_market_agent/DEPLOY_FLY.md` §6), then:

```bash
fly machine start 7812565f9d3378 -a ik-market-research-weekly
fly logs -a ik-market-research-weekly
fly machine status 7812565f9d3378 -a ik-market-research-weekly   # wait for stopped + exit_code 0
```

A full run takes ~10 min at 4GB and uses Max-plan LLM quota (+ a few cents of
Apify for Reddit). Do **not** use `fly machine run . …` for a refresh.

## 7. Verify + run_id semantics

```sql
SELECT 'social' t, run_id, run_date, COUNT(*) n FROM `ik-marketing-data.Market_Research.social_trends`     GROUP BY 2,3
UNION ALL SELECT 'blog', run_id, run_date, COUNT(*) FROM `ik-marketing-data.Market_Research.blog_publications` GROUP BY 2,3
UNION ALL SELECT 'comp', run_id, run_date, COUNT(*) FROM `ik-marketing-data.Market_Research.competitor_intel`  GROUP BY 2,3
UNION ALL SELECT 'exec', run_id, run_date, COUNT(*) FROM `ik-marketing-data.Market_Research.executive_summary` GROUP BY 2,3
ORDER BY run_date DESC;
```

- With `MR_CADENCE=monthly` (Fly) the run_id is `monthly-YYYY-MM` of the **run**
  date (UTC). The run on 2026-11-02 writes `monthly-2026-11` with a rolling
  32-day window (2026-10-01 .. 2026-11-02).
- Every run in the same calendar month shares that run_id, and `bq.write_snapshot`
  DELETEs the run_id before appending — so a retry on the 3rd **replaces** the
  2nd's rows: one snapshot per month. (Before 2026-10-27 the id was
  `weekly-YYYY-MM-DD`, so a retry on another day added a second snapshot.)
- Locally the default is still `weekly-YYYY-MM-DD`; `MR_RUN_ID` forces an
  explicit id. Consumers read `MAX(run_date)`; none filters on the prefix.
- DELETE-then-append is not atomic: a crash between the two leaves that run_id
  empty until a rerun.

## Notes

- **One Machine per pipeline:** this one (2nd of the month) + the job-market one
  (1st, `../job_market_agent`). Both write the same `Market_Research` dataset.
- **Image size:** installs Node + `@anthropic-ai/claude-code`. First build is a
  few minutes; cached after.
- **Rate limits:** `MR_LLM_CONCURRENCY` bounds parallel `claude -p` calls so a run
  stays within Max-plan limits. Lower it if you see throttling in logs.
- **Ephemeral FS:** `output/*.json` snapshots vanish on stop — BigQuery is the
  durable store.
- **Token rotation:** `CLAUDE_CODE_OAUTH_TOKEN` (set ~2026-08-25) is long-lived but
  does expire; when it does, the run exits 1 (blog/competitor/exec 0 rows). Re-run
  `claude setup-token`, `fly secrets set … --stage`, `fly secrets deploy`, then §4.
