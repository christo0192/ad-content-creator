---
task: T03 (consolidated S02+S03+S04 — UI build)
status: complete
duration: ~60min
verification: build_pass, dev_render_pass (5 routes 200, 0 console errors), visual_pass
---
Built the full read-only dashboard UI on the verified BQ data layer.
- `src/lib/queries.ts` — typed query functions + aggregates (jobs by role/family/tier/seniority, top skills via UNNEST, social by source/category, blog by urgency/curriculum-match, competitors, overview stats, job stats).
- Layout: fixed sidebar (lucide icons, active state), Inter + JetBrains Mono, header with latest run_date + "Live from BigQuery" pill, footer.
- Pages (all `force-dynamic`): `/` Overview (5 KPI cards + Executive Priorities hero cards), `/jobs` (4 charts + KPIs + table), `/social` (sentiment/category charts + table), `/blog` (urgency/curriculum charts + table w/ badges), `/competitor` (battlecard: price/duration/ad-intensity + IK-wins vs IK-gaps).
- Charts: recharts, muted indigo+slate palette. Components hand-rolled Tailwind (clean, shadcn-quality) — avoided shadcn to dodge Tailwind-v4/Next-16 friction.
- Null/empty handled (em-dash, EmptyState); INR salary formatting; external links new-tab.

Verified: `npm run build` clean; dev server renders all 5 routes 200 with 0 console errors; Overview screenshot reviewed — professional and usable.
