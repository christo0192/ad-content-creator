"""Executive Summary synthesis (the orchestrator's strong-LLM step).

Reads the 4 validated tabs (Social/Blog/Competitor in-memory + the latest
monthly Job-Market snapshot from BigQuery) and asks Sonnet 4.6 via `claude -p`
to produce a ranked strategic-priorities matrix. Each priority validates against
schemas.ExecPriorityRow.
"""
from __future__ import annotations
import os, sys, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "shared")))

import config as C
import schemas as S
import llm as L
from pydantic import ValidationError

JOBS_TABLE = f"{C.BQ_PROJECT}.{C.BQ_DATASET}.{os.getenv('MR_TBL_JOBS', 'job_market_demand')}"


def jobs_digest(limit_roles: int = 12) -> str:
    """Top AI/ML roles by demand from the latest job-market snapshot in BQ."""
    try:
        import bq as BQ
        cl = BQ.client()
        sql = f"""
          WITH latest AS (SELECT MAX(run_date) d FROM `{JOBS_TABLE}`)
          SELECT normalized_role, COUNT(*) n, COUNTIF(is_emerging) emerging
          FROM `{JOBS_TABLE}` WHERE run_date=(SELECT d FROM latest) AND in_window
          GROUP BY normalized_role ORDER BY n DESC LIMIT {limit_roles}"""
        rows = [dict(r) for r in cl.query(sql).result()]
        if not rows:
            return "No job-market snapshot available yet."
        return "; ".join(f"{r['normalized_role']}: {r['n']} postings ({r['emerging']} emerging)"
                         for r in rows)
    except Exception as e:
        return f"(jobs snapshot unavailable: {str(e)[:80]})"


def _digest_social(rows, n=15):
    rows = sorted(rows, key=lambda r: r.engagement_value or 0, reverse=True)[:n]
    return "; ".join(f"{r.source}:{r.topic} ({r.engagement})" for r in rows)


def _digest_blog(rows, n=15):
    return "; ".join(f"[{r.urgency}/{r.curriculum_match}] {r.recommended_skill} <- {r.title[:50]}"
                     for r in rows[:n])


def _digest_comp(rows):
    out = []
    for r in rows:
        out.append(f"{r.competitor} ({r.program[:40]}; price {r.price_inr}; "
                   f"IK-gaps:{','.join(r.ik_gaps[:2])}; IK-wins:{','.join(r.ik_advantages[:2])})")
    return " | ".join(out)


PROMPT = """You are head of strategy for Interview Kickstart (IK) India, a premium live AI/ML upskilling +
tech-interview-prep EdTech. Synthesize the month's market research into the TOP {k} ranked strategic
priorities. Be specific and decision-ready; ground each in the data below.

JOB MARKET DEMAND (LinkedIn, India): {jobs}

SOCIAL / TECH TRENDS: {social}

BLOG & PUBLICATION SIGNALS (skill -> urgency/curriculum-match): {blog}

COMPETITOR BATTLECARD: {comp}

Return ONLY a JSON array of exactly {k} objects, ranked 1..{k}, no prose:
[{{"rank": <int>,
   "direction": "<short strategic direction>",
   "sections": ["<which tabs support it: Social|Blog|Jobs|Competitor>"],
   "urgency": "<CRITICAL|HIGH|MEDIUM>",
   "gap_vs_competitors": "<gap or '' >",
   "actionable_insight": "<concrete action IK should take>",
   "effort_estimate": "<Low|Medium|High + brief>",
   "revenue_impact": "<brief>",
   "supporting_data": "<cite specific numbers/items above>"}}]"""


def synthesize(social_rows, blog_rows, comp_rows, run_id: str, k: int = 6) -> list:
    prompt = PROMPT.format(
        k=k, jobs=jobs_digest(),
        social=_digest_social(social_rows) or "(none)",
        blog=_digest_blog(blog_rows) or "(none)",
        comp=_digest_comp(comp_rows) or "(none)")
    try:
        data = L.extract_json(prompt, model=C.SYNTH_MODEL, timeout=360)
    except Exception as e:
        print(f"[exec] synthesis failed: {e}")
        return []
    if isinstance(data, dict):
        data = data.get("priorities") or [data]
    rows = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            rows.append(S.ExecPriorityRow(
                run_id=run_id, run_date=C.REPORT_DATE, source="synthesis",
                rank=item.get("rank", len(rows) + 1),
                direction=str(item.get("direction", ""))[:300],
                sections=[str(x) for x in item.get("sections", [])],
                urgency=item.get("urgency", "MEDIUM"),
                gap_vs_competitors=str(item.get("gap_vs_competitors", ""))[:500] or None,
                actionable_insight=str(item.get("actionable_insight", ""))[:1000],
                effort_estimate=str(item.get("effort_estimate", ""))[:200] or None,
                revenue_impact=str(item.get("revenue_impact", ""))[:300] or None,
                supporting_data=str(item.get("supporting_data", ""))[:1000] or None))
        except ValidationError as e:
            print(f"[exec] drop priority: {str(e)[:100]}")
    rows.sort(key=lambda r: r.rank)
    return rows
