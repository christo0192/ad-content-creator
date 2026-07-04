# Project — AI/ML India Market Research Dashboard

Frontend UI dashboard over the Market Research Agent's BigQuery output
(`ik-marketing-data.Market_Research`). Visualizes the 5 tabs the agents produce:

| Table | What it shows |
|---|---|
| `job_market_demand` | LinkedIn AI/ML role demand, salaries, seniority, skills (monthly) |
| `social_trends` | GitHub/HN/PyPI/npm trending AI topics + sentiment (weekly) |
| `blog_publications` | Article signals -> recommended skill / urgency / curriculum match (weekly) |
| `competitor_intel` | Great Learning/Scaler/UpGrad/Udacity/Emeritus battlecard (weekly) |
| `executive_summary` | Ranked strategic priorities synthesized across tabs (weekly) |

**Audience:** IK India marketing/strategy. **Goal:** at-a-glance market view +
drill-down per tab + month-over-month trend (partitioned by `run_date`).

**Backend is DONE** (see `market_research/` + `job_market_agent/`). This milestone
is the read-only dashboard only.
