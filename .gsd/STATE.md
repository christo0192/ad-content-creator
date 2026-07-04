# GSD State

**Phase**: paused — deployment pending (resume in a few days)
**Active Milestone**: M001 — Market Research Dashboard ✅ COMPLETE
**Next Milestone**: M002 — Deploy end-to-end (Vercel + 2 Fly Machines)
**Last Updated**: 2026-06-26

## Resume here
Read **`PROJECT_TODO.md`** (project root) — the full end-to-end completion checklist.

## What's left (all staged; blocked only on 2 user tokens)
1. Vercel dashboard deploy (no blocker) — `market_research_dashboard/DEPLOY.md`.
2. Fly: Job Market (monthly) — needs Apify acct#2 token in `C:\Users\Admin\.secrets\apify_acct2.token`.
3. Fly: Weekly pipeline — needs `claude setup-token` -> `C:\Users\Admin\.secrets\claude_oauth.token` (or ANTHROPIC_API_KEY path).
4. Read-only dashboard SA — data-team request sent (`job_market_agent/IAM_REQUEST.md`).

## Done
- Both pipelines built + verified locally; BQ Market_Research live (5 tables).
- Dashboard built, pushed to PRIVATE GitHub `christo0192/ik-market-research-dashboard`, ran on :3000 (dev server now stopped).
- Sandbox cleaned. flyctl authed; Dockerfiles/fly.toml ready.
