# S01 — Scaffold + BigQuery data layer

## Tasks
- [ ] **T01: Scaffold Next.js app + BQ data layer + health route** `est:25min`
  Depends on: Independent
  Instructions: see T01-PLAN.md. Acceptance: `npm run build` passes; `npm run dev`
  + GET `/api/health` returns live row counts for the 5 Market_Research tables.

- [ ] **T02: Typed query functions per tab** `est:15min`
  Depends on: T01
  Instructions: `lib/queries.ts` — one typed function per table returning the
  latest-`run_date` snapshot + a list of available run_dates, plus small
  aggregates (jobs demand-by-role, social sentiment-by-source). Used by S02-S04.
