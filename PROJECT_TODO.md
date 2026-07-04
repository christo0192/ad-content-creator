# Market Research Agent — Completion TODO (resume doc)

**Last updated:** 2026-06-26
**Goal:** AI/ML India market-research system → BigQuery → dashboard, running
autonomously (weekly + monthly) with a live Vercel dashboard.

> **To resume:** read this file + `.gsd/STATE.md`. Everything below is staged;
> what's left is 3 deploys + 1 data-team request, blocked only on 2 tokens.

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
| **Fly deploy — Job Market (monthly)** | ⬜ TODO (#2) — needs Apify token |
| **Fly deploy — Weekly** | ⬜ TODO (#3) — needs Claude OAuth token (or API key) |
| **Read-only dashboard SA** | ⬜ TODO (#4) — data-team request sent |

Nothing auto-refreshes the data yet — dashboard shows rows from manual runs.

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

## #2 — Deploy Fly: Job Market (monthly)  [needs Apify token]
Guide: `job_market_agent/DEPLOY_FLY.md`. Pure Python, low risk.
- [ ] `cd job_market_agent`; `fly apps create ik-market-research-jobs`
- [ ] Set secrets (Claude can run this via `fly secrets import` from the token file + generated BQ b64 — no echo):
  - `MARKET_RESEARCH_BQ_SA_B64` (base64 of the writer key)
  - `APIFY_TOKEN` (from `apify_acct2.token`)
- [ ] `fly deploy --ha=false`
- [ ] `fly machine run . --schedule monthly --restart no --region sin -a ik-market-research-jobs`
- [ ] Verify: `fly machine run . --command "python run_monthly.py"` → rows in BQ for new run_date.

## #3 — Deploy Fly: Weekly pipeline  [needs Claude OAuth token OR API key]
Guide: `market_research/DEPLOY_FLY.md`. Image bundles Node + Claude Code CLI. **Riskiest** — verify `claude -p` works headless in-container first.
- [ ] `cd market_research`; `fly apps create ik-market-research-weekly`
- [ ] Set secrets: `MARKET_RESEARCH_BQ_SA_B64`, `APIFY_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN` (or `ANTHROPIC_API_KEY` if API path).
- [ ] `fly deploy --ha=false`
- [ ] **Smoke-test `claude -p` in the container BEFORE scheduling:**
      `fly machine run . --command "claude -p --model haiku --output-format text 'reply: pong'"`
      → if it fails, fall back to the API-key path; do not schedule until green.
- [ ] `fly machine run . --schedule weekly --restart no --region sin -a ik-market-research-weekly`
- [ ] Verify: `fly machine run . --command "python run_weekly.py"` → 4 weekly tabs + exec land for the new run_date.
- [ ] On Fly's dedicated CPU, raise `MR_LLM_CONCURRENCY` to 2 (env) for faster runs.

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
