# T01 — Scaffold Next.js app + BQ data layer + health route

## Goal
Stand up the dashboard project with a working, server-side BigQuery connection.

## Location
Create the app at `market_research_dashboard/` (sibling of `market_research/`).

## Steps
1. Scaffold **Next.js (App Router) + TypeScript + Tailwind** (`create-next-app`,
   non-interactive: ts, tailwind, eslint, app router, src dir, import alias `@/*`).
2. Add deps: `@google-cloud/bigquery`. (shadcn/Recharts added in later slices.)
3. `src/lib/bq.ts` — a singleton BigQuery client:
   - Credentials precedence: env `MARKET_RESEARCH_BQ_SA_B64` (base64 JSON) ->
     local file `C:\\Users\\Admin\\.gcp-keys\\market-research-bq.json`.
   - project `ik-marketing-data`. Export `bq` client + a `query<T>(sql)` helper.
   - Constants: `DATASET = "Market_Research"`, table names.
4. `src/app/api/health/route.ts` — Route Handler (force-dynamic, nodejs runtime)
   that queries `__TABLES__` and returns `{ table_id, row_count }[]` as JSON.
5. `.env.local.example` documenting `MARKET_RESEARCH_BQ_SA_B64`.
6. `README.md` — run instructions + the prod env var.

## Constraints
- BigQuery access is SERVER-SIDE ONLY. Never import `@/lib/bq` into a client
  component. Route handlers / server components only. `export const runtime = "nodejs"`.
- Do not commit any key; `.gitignore` must cover `.env*` and `*.json` keys.

## Acceptance
- `npm run build` succeeds (no type errors).
- `npm run dev` then `GET http://localhost:3000/api/health` returns the 5 tables
  with row counts (job_market_demand ~442, social_trends ~42, blog_publications
  ~23, competitor_intel ~5, executive_summary ~6).
- Report files created + the health output.
