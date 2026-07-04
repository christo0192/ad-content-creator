# M001 — Market Research Dashboard

Read-only Next.js dashboard over `ik-marketing-data.Market_Research` (5 tables).
Slices ordered by risk (foundation/BQ-auth first).

## Slices

- **S01 — Scaffold + BigQuery data layer** `risk:high`
  Next.js app, Tailwind/shadcn, `@google-cloud/bigquery` client with base64-env
  SA loader, typed query functions for all 5 tables, a `/api/health` proving the
  live BQ connection (row counts). Acceptance: `npm run build` passes + health
  route returns the 5 table counts locally.

- **S02 — Dashboard shell + Overview** `risk:med`
  App layout, sidebar nav (Overview/Jobs/Social/Blog/Competitor), Overview page:
  KPI cards (counts, latest run dates) + Executive Summary priorities list.

- **S03 — Per-tab data views** `risk:med`
  Jobs, Social, Blog, Competitor pages: sortable/filterable tables of the latest
  snapshot, with the key columns + external reference links.

- **S04 — Charts + trends** `risk:med`
  Recharts: jobs demand-by-role + role-family + top skills; social sentiment by
  source; competitor price/duration compare; MoM trend by `run_date`.

- **S05 — Deploy + docs** `risk:low`
  Vercel config, env wiring (`MARKET_RESEARCH_BQ_SA_B64`), README, and the
  read-only dash-SA follow-up note.
