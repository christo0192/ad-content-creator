# cloudflare-trigger/ — `ik-intelligence-trigger` (NOT scheduled)

> **Status (2026-10-27): deployed once, cronless. It schedules nothing.**
> The live monthly dispatch of the two Intelligence Fly machines runs in
> **`christo0192/ik-mis` → `cloudflare-trigger/`** (Worker
> **`ik-ad-generator-trigger`**). This folder stays in the repo, tested by CI,
> so it can be re-enabled on a paid Workers plan (see below).

## Why it has no cron

Cloudflare refused this Worker's cron `30 3 1,2 * *` with code **10072**:
*"This account has reached the Workers Free limit of 5 cron triggers per
account"*. Account `bbb3aa03755ccab33b6367bb6367294c` is on Workers Free and
its 5 slots are all taken by live Workers:

| Worker | cron(s) |
|---|---|
| `ik-ad-generator-trigger` (ik-mis) | `30 5 * * *` |
| `ik-anomaly-trigger` | `30 4 * * *` |
| `ik-donna-scheduler` | 2 crons |
| `sip-pipeline-trigger` | `30 3 * * *` |

Decision: stay on the free plan and piggyback on a cron that already exists,
instead of paying for Workers Paid or giving up another Worker's slot.

## Where the live dispatch lives

`ik-mis/cloudflare-trigger` (Worker `ik-ad-generator-trigger`, cron
`30 5 * * *` = **05:30 UTC / 11:00 IST**, daily). Besides its daily start of
`ik-ad-generator` (`FLY_APP` / `FLY_MACHINE_ID` / `FLY_TOKEN`, unchanged and
independent of the starts below), it dispatches on the UTC day of the month:

| UTC day | starts | app | machine | Worker secret |
|---|---|---|---|---|
| 1 | jobs agent (`job_market_agent/`) | `ik-market-research-jobs` | `7845393fe26338` | `FLY_TOKEN_JOBS` |
| 2 | market-research pipeline (`market_research/`) | `ik-market-research-weekly` | `7812565f9d3378` | `FLY_TOKEN_WEEKLY` |

Jobs still go a day before the pipeline, whose Executive Summary reads the
latest `job_market_demand` snapshot. 05:30 UTC keeps the UTC and IST calendar
dates equal (anything 00:00-18:29 UTC does), so "the 1st" is the 1st in both.

Token setup, checks and machine-ID changes are in
`../job_market_agent/DEPLOY_FLY.md` §5 and `../market_research/DEPLOY_FLY.md` §5.
Never set a Fly-native `--schedule` on either machine: the ik-mis Worker is the
only scheduler.

## What is deployed here

`ik-intelligence-trigger` was deployed once and exists on the account without a
cron trigger, so it never fires. Do **not** give it a cron while the ik-mis
Worker dispatches the same machines, or each month's jobs and pipeline would
start twice (two paid runs). If it should not linger, `npx wrangler delete`
from this folder removes it; nothing depends on it.

## Code + tests (kept as they are)

- `src/index.ts`: cron `CRON = "30 3 1,2 * *"`, UTC day 1 starts jobs, day 2
  starts the pipeline, any other day logs and starts nothing; transient
  failures (5xx / 429 / network / 15 s timeout) retried up to 3 attempts; never
  throws.
- `test/index.test.ts`: vitest suite, including a guard that `CRON` equals
  `wrangler.toml [triggers].crons[0]`.
- CI runs `npm ci && npm test && npm run typecheck` here.

```bash
cd cloudflare-trigger
npm ci && npm test && npm run typecheck
```

## Re-enabling it on Workers Paid

Only if the account moves to **Workers Paid** (cron limit is no longer 5) **and**
the day-1 / day-2 dispatch is removed from `ik-mis/cloudflare-trigger` in the
same change (never both live):

```bash
cd cloudflare-trigger
npm ci
npx wrangler login          # once; or CLOUDFLARE_API_TOKEN with Workers Scripts:Edit
fly tokens create deploy -a ik-market-research-jobs   -n ik-intelligence-trigger -x 26280h | npx wrangler secret put FLY_TOKEN_JOBS
fly tokens create deploy -a ik-market-research-weekly -n ik-intelligence-trigger -x 26280h | npx wrangler secret put FLY_TOKEN_WEEKLY
npx wrangler deploy         # output must list the schedule "30 3 1,2 * *"
```

`-x 26280h` = 3 years; record the creation date. 03:30 UTC (09:00 IST) runs
before `ik-ad-generator` (05:30 UTC) reads `Market_Research`. Check a fired run
with `npx wrangler tail ik-intelligence-trigger` (`jobs start OK (200)` on the
1st, `weekly start OK (200)` on the 2nd). Then update both `DEPLOY_FLY.md`
files, `../PROJECT_TODO.md` and `../.gsd/STATE.md` back to this Worker.
