# GSD State

**Phase**: active — Intelligence dept of the IK MIS closed-loop system (was: standalone market-research project)
**Active Milestone**: M002 — Deploy Intelligence pipelines end-to-end (Vercel deploy superseded; 2 Fly deploys still pending)
**Last Updated**: 2026-07-04

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
   - Fly: Job Market (monthly) — Apify acct#2 token (`C:\Users\Admin\.secrets\apify_acct2.token`).
   - Fly: Weekly pipeline — **unblocked**: `claude -p` OAuth on Fly is PROVEN
     (MIS spike passed 2×; pattern + `ANTHROPIC_API_KEY` fallback documented in
     `MIS/spikes/claude-p-fly/` incl. `llm_fallback.patch.md` for `shared/llm.py`).
   - Read-only dashboard SA — data-team request (`job_market_agent/IAM_REQUEST.md`).
3. **Freshness matters now more than before**: the MIS Generation dept consumes
   `Market_Research.*` weekly — until the Fly deploys ship, refresh via manual runs.

## Done
- Both pipelines built + verified locally; BQ Market_Research live (5 tables).
- Consumed by MIS Generation conductor (live-verified 2026-07-04: all 5 tables fed the
  first live generation cycle successfully).
- Reuse exports: `shared/llm.py`/`bq.py`/`schemas.py` patterns + `job_market_agent`
  skills vocabulary were the seeds for the MIS Generation dept.
- Dashboard M001 complete → superseded by MIS Mission Control (see above).
