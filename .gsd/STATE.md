# GSD State

**Phase**: active — Intelligence dept of the IK MIS closed-loop system (was: standalone market-research project)
**Active Milestone**: M002 — Deploy Intelligence pipelines end-to-end (Vercel deploy superseded). Both Fly apps exist (2026-08-25) but are now **Worker-triggered** by the MIS Worker `ik-ad-generator-trigger` (ik-mis `cloudflare-trigger/`, 05:30 UTC: day 1 jobs, day 2 pipeline); this repo's own Worker is cronless (see below)
**Last Updated**: 2026-10-27

## 2026-10-27 — staleness incident + fix (branch `feat/intelligence-monthly-trigger`, merged as #2)
- **Incident:** the 5 `Market_Research` tables went stale (jobs last `naukri-2026-08`,
  run_date 2026-08-18; the other 4 last `weekly-2026-08-25`). The Fly-native
  `--schedule monthly` on both machines **never fired** (Aug-Oct missed), and the
  jobs app's secrets were only "Staged" (label quirk of a non-Launch machine).
- **Fix (code merged, scheduler deploy pending in ik-mis):**
  - **Scheduler = MIS Worker `ik-ad-generator-trigger`** (`christo0192/ik-mis` →
    `cloudflare-trigger/`, cron `30 5 * * *` = 05:30 UTC / 11:00 IST). Its daily
    `ik-ad-generator` start is unchanged and independent; on UTC day 1 it also starts
    jobs machine `7845393fe26338` (`ik-market-research-jobs`), on day 2 pipeline machine
    `7812565f9d3378` (`ik-market-research-weekly`). Secrets `FLY_TOKEN_JOBS` /
    `FLY_TOKEN_WEEKLY` = app-scoped Fly deploy tokens. Never throws (CF retry = double run).
  - This repo's own `cloudflare-trigger/` Worker (same dispatch on its own monthly
    cron) was deployed once but is **cronless**: Cloudflare
    refused the cron (code 10072 — Workers Free limit of 5 crons per account; slots:
    ik-ad-generator-trigger, ik-anomaly-trigger, ik-donna-scheduler x2,
    sip-pipeline-trigger). Decision: stay free, piggyback on the MIS cron. Code + vitest
    suite kept (CI) for a Workers Paid re-enable — see `cloudflare-trigger/README.md`.
    Never give it a cron while ik-mis dispatches (double runs).
  - `--preflight` on both entrypoints (secrets + BQ `SELECT 1`; pipeline also one
    tiny `claude -p`), and real exit codes: jobs 2 = preflight failed (before any
    Apify spend), 3 = live run with 0 rows; pipeline 2 = preflight, 1 = degraded tab.
  - Pipeline run_id grain: `MR_CADENCE=monthly` on Fly → `monthly-YYYY-MM` (a retry
    the same month replaces rows; local default still `weekly-YYYY-MM-DD`).
  - `[[restart]] policy="never"` in both fly.toml; claude-code CLI pinned 2.1.311 on Node 24.
  - First tests + CI (`.github/workflows/ci.yml`, `ruff.toml`): pytest per package
    (two processes — duplicate `config` module), offline dry-run smoke, vitest Worker suite.
- **Deploy (manual, needs the user):** follow `job_market_agent/DEPLOY_FLY.md` §3-5 and
  `market_research/DEPLOY_FLY.md` §3-5 — build-only + `machine update` for jobs (NEVER
  plain `fly deploy` there), `fly deploy --ha=false` for the pipeline, clear schedules
  via `{"schedule":""}`, `--preflight` smokes, then in the ik-mis `cloudflare-trigger/`
  folder: `wrangler login` + the two token pipes (`… | npx wrangler secret put
  FLY_TOKEN_JOBS` / `FLY_TOKEN_WEEKLY`) + the ik-mis Worker deploy (§5 of both guides).
  Optional ad-hoc refresh: start jobs, wait exit 0, then pipeline.
- **First automatic runs:** 2026-11-01 (jobs → `naukri-2026-11`) and 2026-11-02
  (pipeline → `monthly-2026-11`) at 11:00 IST, if the ik-mis dispatch is deployed by then.
  On those two days the same-cron Generation run may still read the previous snapshot.

## Big picture change (2026-07-04)
This project is now the **Intelligence department** of the 3-department IK MIS system
(Intelligence + Performance/PMIS + Generation), coupled via BigQuery `ik-marketing-data`.
The system plan, dashboard, and cross-cutting docs live in `C:\Users\Admin\Claude projects\MIS`
(github: `christo0192/ik-mis`, private). Read `MIS/PLAN.md` + `MIS/docs/ARCHITECTURE.md` first.

## Version control (NEW 2026-07-04)
- This project root is now a git repo → **github.com/christo0192/ad-content-creator** (private),
  first commit `ec82233` (126 files). Renamed from `ik-market-research-dashboard`.
- `market_research_dashboard/` is **legacy** and gitignored here: the restructured MIS
  Mission Control dashboard (which subsumes it) lives in `ik-mis/dashboard/` and is
  deployed on Vercel by the user. Old dashboard history preserved on this repo's
  `legacy-dashboard` branch; the MIS restructure branch is `mis-mission-control`.

## Resume here
1. `MIS/PLAN.md` status log — Phase 1 of the MIS system is COMPLETE & LIVE
   (daily cron 11:00 IST → Fly `ik-ad-generator` runs the Generation chain, which READS
   this project's `Market_Research` tables as generation signals).
2. This project's own remaining work = original M002 minus the dashboard:
   - Fly apps + secrets exist since 2026-08-25; the 2026-10-27 branch is merged (#2).
     What's left: the Fly redeploys (§3-4), the day-1/day-2 dispatch + two token secrets
     in ik-mis `cloudflare-trigger/` (§5), and confirming the 11-01/11-02 runs.
   - Read-only dashboard SA — data-team request (`job_market_agent/IAM_REQUEST.md`).
3. **Freshness matters now more than before**: the MIS Generation dept consumes
   `Market_Research.*` — until the ik-mis dispatch is live, refresh via an ad-hoc
   `fly machine start` (DEPLOY_FLY.md §6; jobs first, then the pipeline).

## Done
- Both pipelines built + verified locally; BQ Market_Research live (5 tables).
- Consumed by MIS Generation conductor (live-verified 2026-07-04: all 5 tables fed the
  first live generation cycle successfully).
- Reuse exports: `shared/llm.py`/`bq.py`/`schemas.py` patterns + `job_market_agent`
  skills vocabulary were the seeds for the MIS Generation dept.
- Dashboard M001 complete → superseded by MIS Mission Control (see above).
- 2026-08-25: both Fly apps created + images deployed (from the then-unmerged
  `feat/naukri-jobs-source` commits, now cherry-picked onto the 10-27 branch).
