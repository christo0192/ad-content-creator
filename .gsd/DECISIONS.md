# Architectural Decisions (append-only)

## D001 — Stack: Next.js + TS + Tailwind + shadcn/ui (2026-06-25)
Matches the user's established stack and the existing SIP dashboard precedent
(Next.js on Vercel). App Router. Charts via Recharts.

## D002 — BigQuery access is server-side only (2026-06-25)
Route Handlers / Server Components query BQ with `@google-cloud/bigquery`. The
SA key is loaded from a base64 env var (`MARKET_RESEARCH_BQ_SA_B64`), never
shipped to the client. No public BQ credentials, no client-side queries.

## D003 — Reuse `market-research-bq@` SA for reads (interim) (2026-06-25)
The dashboard reads `Market_Research` via the existing `market-research-bq` SA
(it has read on that dataset). FOLLOW-UP: provision a dedicated read-only
`market-research-dash-bq@` (dataViewer + jobUser) before production so the
dashboard key cannot write. Tracked in KNOWLEDGE.

## D004 — Deploy target: Vercel (2026-06-25)
Mirrors the SIP dashboard. Env secrets: `MARKET_RESEARCH_BQ_SA_B64`. Local dev
reads the key file at `C:\Users\Admin\.gcp-keys\market-research-bq.json`.

## D005 — Read latest snapshot by default, trends via run_date (2026-06-25)
Each page shows the latest `run_date` partition by default; trend views
aggregate across `run_date` (MoM). Jobs is monthly; others weekly.

## D006 — Private GitHub repo + hand-rolled UI (2026-06-26)
Repo `christo0192/ik-market-research-dashboard` (PRIVATE), Next app at root for
Vercel auto-detect. Scaffold landed on Next 16 + Tailwind v4; chose hand-rolled
Tailwind components over shadcn to avoid v4/16 friction. Stray `server.out.log`
removed from tracking; `*.log` ignored.
