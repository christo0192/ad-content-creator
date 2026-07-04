# Knowledge — patterns & lessons (append-only)

## K001 — BQ tables + key columns (source of truth: market_research/shared/schemas.py)
- `job_market_demand`: run_id, run_date(DATE, MONTH-partition), title,
  normalized_role, role_family, company, company_tier, location, seniority_level,
  employment_type, applicants_count(INT), salary_min_inr, salary_max_inr,
  posted_date, in_window(BOOL), is_emerging(BOOL), lenses[STR], skills[STR],
  reference_url. (~442 rows, run_id `linkedin-2026-06`.)
- `social_trends`: run_id, run_date, source, topic, sentiment(1-5), engagement,
  engagement_value(INT), category, reference_url. (~42)
- `blog_publications`: run_id, run_date, publication, title, recommended_skill,
  audience, urgency, curriculum_match, published_date, summary, reference_url. (~23)
- `competitor_intel`: run_id, run_date, competitor, program, price_inr,
  duration_months, curriculum_overview, key_tools[], hands_on_projects,
  certifications, mentor_quality, curriculum_gaps_vs_ik[], ik_advantages[],
  ik_gaps[], ad_intensity(1-5), reference_url. (~5)
- `executive_summary`: run_id, run_date, rank, direction, sections[], urgency
  (CRITICAL/HIGH/MEDIUM), gap_vs_competitors, actionable_insight, effort_estimate,
  revenue_impact, supporting_data. (~6)
- REPEATED columns (skills/lenses/key_tools/...) come back as JS arrays.

## K002 — BQ auth in Next (mirror CAI bq_client precedence)
SA loader precedence: `MARKET_RESEARCH_BQ_SA_B64` (base64 JSON) -> local key file
`C:\Users\Admin\.gcp-keys\market-research-bq.json`. project=`ik-marketing-data`.
The `market-research-bq` SA has jobUser + dataEditor on Market_Research (read OK).

## K003 — FOLLOW-UP: dedicated read-only dashboard SA
Before production, ask data team for `market-research-dash-bq@` (jobUser +
dataViewer on Market_Research) so the dashboard key cannot write. See
job_market_agent/IAM_REQUEST.md optional block.
