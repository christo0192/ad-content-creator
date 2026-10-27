# Market Research Agent — Completion TODO (resume doc)

**Last updated:** 2026-10-27
**Goal:** AI/ML India market-research system → BigQuery → dashboard, running
autonomously (monthly: jobs on the 1st, pipeline on the 2nd) — the dashboard is
now MIS Mission Control (`ik-mis/dashboard`).

> **To resume:** read this file + `.gsd/STATE.md`. **2026-10-27 update:** both Fly
> apps were created on 2026-08-25, but their Fly-native `--schedule` never fired
> (data stale since 2026-08-25). The scheduler is now the Cloudflare Worker
> `ik-intelligence-trigger` (`cloudflare-trigger/`, branch
> `feat/intelligence-monthly-trigger`). #2/#3 below are rewritten for that flow;
> the old `fly machine run . --schedule …` steps are obsolete and must NOT be re-run.

---

## Status snapshot

| Component | State |
|---|---|
| Job Market pipeline (`job_market_agent/`, monthly, LinkedIn) | ✅ built + verified locally |
| Weekly pipeline (`market_research/`, Social/Blog/Competitor + Exec) | ✅ built + verified locally |
| BigQuery `ik-marketing-data.Market_Research` (5 tables) | ✅ live (442/42/23/5/6 rows) |
| Writer SA `market-research-bq@` | ✅ provisioned + verified |
| Dashboard (`market_research_dashboard/`, Next.js) | ✅ built; runs locally; pushed to private GitHub |
| `cai_dev_sandbox` cleanup | ✅ done |
| **Vercel deploy** | ⬜ TODO (#1) |
| **Fly deploy — Job Market (monthly)** | 🟡 app + machine exist (2026-08-25); Worker-trigger redeploy pending (#2) |
| **Fly deploy — Pipeline (monthly)** | 🟡 app + machine exist (2026-08-25); Worker-trigger redeploy pending (#3) |
| **Cloudflare Worker `ik-intelligence-trigger`** | ⬜ TODO (#5) — needs Cloudflare auth (`wrangler login`) |
| **Read-only dashboard SA** | ⬜ TODO (#4) — data-team request sent |

Nothing auto-refreshes the data yet — the 2026-08 Fly schedules never fired;
auto-refresh starts once #5 is deployed (first runs 2026-11-01 / 2026-11-02).

---

## BLOCKERS — tokens

Place in `C:\Users\Admin\.secrets\` (created, gitignored, outside any repo):

**a) Apify acct #2 (`hip_bouncer`) API token** ✅ DONE 2026-06-29 — saved at
`C:\Users\Admin\.secrets\apify_acct2.token`. Validated (acct hip_bouncer, ~$3.5/$5
used). Reddit now LIVE in the Social tab (21 rows; ~$0.004/item via
`trudax/reddit-scraper-lite`). **This also unblocks Fly #2.** (If lost, re-fetch:
Apify console → hip_bouncer → Settings → Integrations → Personal API token.)

**b) Claude Code OAuth token** → unblocks Fly #3 (headless `claude -p` on Fly)
- In a normal terminal (needs browser; do NOT run via `!` — would print the token):
```powershell
claude setup-token
Set-Content -Path "C:\Users\Admin\.secrets\claude_oauth.token" -Value "<paste-token>" -NoNewline
```
- ALTERNATIVE: skip the Max-plan token and run the weekly pipeline on a small
  Anthropic **API key** (~$2–9/mo) on Fly only. If chosen, set `ANTHROPIC_API_KEY`
  as the Fly secret and switch `market_research/shared/llm.py` to API mode (the
  `claude -p` path stays for local). Decide before deploying #3.

---

## #1 — Deploy the dashboard to Vercel  (no token blocker)
Repo: **https://github.com/christo0192/ik-market-research-dashboard** (private). Guide: `market_research_dashboard/DEPLOY.md`.
- [ ] Vercel → Add New → Project → import the repo (Next.js auto-detected, root `./`).
- [ ] Set env var `MARKET_RESEARCH_BQ_SA_B64` (Production + Preview). Generate:
```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\Users\Admin\.gcp-keys\market-research-bq.json"))
```
- [ ] Deploy. Verify `/` (KPIs + priorities) and `/api/health` (5 table counts).
- [ ] (Later) swap the env value to the read-only dash-SA key (#4) — no code change.

## #2 — Fly: Job Market (monthly)  [app `ik-market-research-jobs`, machine `7845393fe26338`]
Guide: `job_market_agent/DEPLOY_FLY.md` (rewritten 2026-10-27). Pure Python, low risk.
- [x] App created, secrets `APIFY_TOKEN` + `MARKET_RESEARCH_BQ_SA_B64` set (2026-08-25; "Staged" label is expected on this non-Launch machine)
- [x] ~~`fly machine run . --schedule monthly`~~ — registered 2026-08-25, **never fired**. Do not re-run.
- [ ] **NEVER plain `fly deploy` here** (creates + starts a new machine = paid scrape). `fly deploy --build-only --push --image-label <tag>` then `fly machine update 7845393fe26338 --image … --machine-config noschedule.json --restart no --skip-start -y` (§3)
- [ ] No-spend smoke: `fly machine run <image> --rm … --command "python run_monthly.py --preflight"` → `preflight OK` (§4)
- [ ] `fly machines list -a ik-market-research-jobs --json` → no `schedule`, restart `no`, stopped

## #3 — Fly: Market-research pipeline (monthly)  [app `ik-market-research-weekly`, machine `7812565f9d3378`]
Guide: `market_research/DEPLOY_FLY.md` (rewritten 2026-10-27). Image bundles Node 24 + Claude Code CLI (pinned 2.1.311).
- [x] App created, secrets `MARKET_RESEARCH_BQ_SA_B64`, `APIFY_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN` deployed (2026-08-25)
- [x] ~~`fly machine run . --schedule weekly/monthly`~~ — registered 2026-08-25, **never fired**. Do not re-run.
- [ ] `fly deploy --ha=false` (Launch machine: updated in place, stays stopped; picks up `MR_CADENCE=monthly` + `[[restart]] never`)
- [ ] Clear the schedule: `fly machine update 7812565f9d3378 --machine-config noschedule.json --restart no --skip-start -y` (§3)
- [ ] Smoke: `fly machine run <image> --rm --vm-memory 4096 … --command "python run_weekly.py --preflight"` → BQ OK + `claude -p` OK + `preflight OK` (§4)
- [ ] On Fly's dedicated CPU, raise `MR_LLM_CONCURRENCY` to 2 (env) for faster runs.

## #5 — Cloudflare Worker `ik-intelligence-trigger` (the ONLY scheduler)  [needs Cloudflare auth]
Code: `cloudflare-trigger/` (cron `30 3 1,2 * *`; UTC day 1 → jobs, day 2 → pipeline).
- [ ] `cd cloudflare-trigger && npm ci && npx wrangler login` (browser OAuth; or `CLOUDFLARE_API_TOKEN`)
- [ ] `fly tokens create deploy -a ik-market-research-jobs -n ik-intelligence-trigger -x 26280h | npx wrangler secret put FLY_TOKEN_JOBS`
- [ ] `fly tokens create deploy -a ik-market-research-weekly -n ik-intelligence-trigger -x 26280h | npx wrangler secret put FLY_TOKEN_WEEKLY`
- [ ] Record the token creation date here (3-year expiry): ____
- [ ] `npx wrangler deploy` → output lists schedule `30 3 1,2 * *`
- [ ] Optional now: ad-hoc refresh — `fly machine start` jobs, wait for exit 0, then the pipeline (~$0.70 Apify + Max-plan usage)
- [ ] 2026-11-01 / 11-02: `npx wrangler tail ik-intelligence-trigger` shows `start OK (200)`; BQ has `naukri-2026-11` + `monthly-2026-11`

## #4 — Read-only dashboard SA  [data-team request — sent 2026-06-26]
Request lives in `job_market_agent/IAM_REQUEST.md` (addendum).
- [ ] Data team: create `market-research-dash-bq@` (jobUser + dataViewer on Market_Research only), key in Secret Manager as `sa-key-market-research-dash-bq`.
- [ ] Fetch + base64 it; update the Vercel `MARKET_RESEARCH_BQ_SA_B64` value. No code change.

---

## Optional follow-ups / known gaps (non-blocking)
- [ ] **TechGig + LiquidMetal AI** blog sources return 0 (JS/anti-scrape walls). Need a Playwright/headless fetch path to cover them.
- [ ] **Reddit** in Social is wired but unverified live — confirms once `APIFY_TOKEN` is set.
- [ ] **Tab1 sentiment** is a magnitude heuristic — could upgrade to a `claude -p` sentiment pass.
- [ ] **Caching**: dashboard pages are `force-dynamic` (live BQ per request). Switch to `revalidate = 3600` to cut BQ scan cost if traffic grows.
- [ ] Local Next.js **dev server** was running on :3000 — stopped on 2026-06-26.

---

## Key paths & references
- Pipelines: `job_market_agent/` (monthly), `market_research/` (weekly).
- Dashboard: `market_research_dashboard/` → DEPLOY.md.
- Fly guides: `*/DEPLOY_FLY.md`. IAM: `job_market_agent/IAM_REQUEST.md`.
- BQ: project `ik-marketing-data`, dataset `Market_Research`, writer key `C:\Users\Admin\.gcp-keys\market-research-bq.json`.
- Secrets dir: `C:\Users\Admin\.secrets\`. GSD state: `.gsd/STATE.md`.
- Architecture: `Market_Research_Agent_Architecture_Plan_v0.1.md`.
- Memory: `~/.claude/projects/<hash>/memory/` (job-market-agent-build, market-research-llm-via-claude-cli, market-research-dashboard).
