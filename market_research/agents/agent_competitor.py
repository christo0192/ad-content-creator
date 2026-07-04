"""Agent 4 — Competitor Intelligence (Tab 4).

Fetches each competitor's flagship AI/ML/DS program page via Jina Reader (free,
handles JS SPAs), then Haiku extraction via `claude -p` -> the 14-col battlecard.
Rows validate against schemas.CompetitorRow (the tool-call gate).

Pricing on these pages is often form-gated -> price_inr may be null with
confidence='low'; that's honest, not a failure.
"""
from __future__ import annotations
import os, sys, json, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shared")))

import config as C
import schemas as S
import fetch as F
import llm as L
from pydantic import ValidationError

# Competitor -> flagship program page (best-effort; update as URLs change).
COMPETITORS = {
    "Scaler": "https://www.scaler.com/data-science-course/",
    "Great Learning": "https://www.mygreatlearning.com/pg-program-data-science-business-analytics-course",
    "UpGrad": "https://www.upgrad.com/data-science-pgc-iiitb/",
    "Simplilearn": "https://www.simplilearn.com/pgp-data-science-certification-training-course",
    "Udacity": "https://www.udacity.com/course/ai-programming-python-nanodegree--nd089",
    "Emeritus": "https://emeritus.org/in/",
}
PAGE_CHARS = int(os.getenv("MR_COMP_PAGE_CHARS", "3500"))
COMP_TIMEOUT_S = int(os.getenv("MR_COMP_TIMEOUT_S", "300"))


def _curriculum_context() -> str:
    try:
        return json.dumps(json.load(open(C.IK_CURRICULUM_JSON, encoding="utf-8")))[:1500]
    except Exception:
        return ("IK India: live Agentic-AI/GenAI/ML upskilling + interview prep, "
                "mentor-led, AWS-centric, FAANG instructors, job-switch focus.")


CURRICULUM = _curriculum_context()

PROMPT = """You are a competitive-intelligence analyst for Interview Kickstart (IK) India, a premium
live AI/ML upskilling + tech-interview-prep EdTech.

IK context (JSON): {curriculum}

Below is the scraped marketing page for competitor "{name}" ({url}).
Extract a competitor battlecard. Use the page where possible; if a field is not on the page,
use your general knowledge but lower confidence. Prices in INR (integer rupees, no commas);
null if genuinely unknown. Return ONLY this JSON object, no prose:
{{"program": "<program name>",
  "price_inr": <int or null>,
  "price_source": "<page | knowledge | unknown>",
  "confidence": "<high | medium | low>",
  "duration_months": <int or null>,
  "curriculum_overview": "<2-3 sentence summary>",
  "key_tools": ["<tool>", ...],
  "hands_on_projects": "<projects/capstones summary>",
  "certifications": "<credential offered>",
  "mentor_quality": "<mentor/instructor model>",
  "curriculum_gaps_vs_ik": ["<what IK covers that they lack>", ...],
  "ik_advantages": ["<where IK wins>", ...],
  "ik_gaps": ["<where they beat IK>", ...],
  "ad_intensity": <int 1-5 estimate of marketing aggressiveness>}}

PAGE CONTENT:
{page}"""


def _listify(v):
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)]


def collect(run_id: str | None = None) -> list:
    rid = run_id or C.RUN_ID
    pages, names = [], []
    for name, url in COMPETITORS.items():
        txt = ""
        try:
            txt = F.jina_reader(url)
        except Exception as e:
            print(f"[competitor] jina fail {name}: {e}")
        # thin page (bot-block/redirect) -> trafilatura/raw fallback
        if len(txt or "") < 1500:
            try:
                alt = F.article_text(url) or F.get_text(url)
                if len(alt or "") > len(txt or ""):
                    txt = alt
            except Exception:
                pass
        if txt and len(txt) > 400:
            pages.append((name, url, txt[:PAGE_CHARS]))
            print(f"[competitor] fetched {name} ({len(txt)} chars)")
        else:
            print(f"[competitor] thin page {name} ({len(txt or '')} chars), skipping")
    if not pages:
        print("[competitor] no pages fetched")
        return []

    prompts = [PROMPT.format(curriculum=CURRICULUM, name=n, url=u, page=p)
               for (n, u, p) in pages]
    t0 = time.time()
    extracted = L.map_extract(prompts, model=C.EXTRACT_MODEL, timeout=COMP_TIMEOUT_S)
    print(f"[competitor] extraction done in {time.time()-t0:.0f}s")

    rows = []
    for (name, url, _), ex in zip(pages, extracted):
        if not isinstance(ex, dict):
            continue
        try:
            rows.append(S.CompetitorRow(
                run_id=rid, run_date=C.REPORT_DATE, source="Jina/DOM",
                competitor=name, program=str(ex.get("program", ""))[:200] or name,
                price_inr=ex.get("price_inr") if isinstance(ex.get("price_inr"), int) else None,
                price_source=str(ex.get("price_source", "unknown"))[:40],
                confidence=ex.get("confidence", "low"),
                duration_months=ex.get("duration_months") if isinstance(ex.get("duration_months"), int) else None,
                curriculum_overview=str(ex.get("curriculum_overview", ""))[:1000],
                key_tools=_listify(ex.get("key_tools")),
                hands_on_projects=str(ex.get("hands_on_projects", ""))[:500],
                certifications=str(ex.get("certifications", ""))[:300],
                mentor_quality=str(ex.get("mentor_quality", ""))[:300],
                curriculum_gaps_vs_ik=_listify(ex.get("curriculum_gaps_vs_ik")),
                ik_advantages=_listify(ex.get("ik_advantages")),
                ik_gaps=_listify(ex.get("ik_gaps")),
                ad_intensity=ex.get("ad_intensity") if isinstance(ex.get("ad_intensity"), int) else 3,
                reference_url=url))
        except ValidationError as e:
            print(f"[competitor] {name} validation drop: {str(e)[:120]}")
    return rows


def main():
    rows = collect()
    print(f"[competitor] {len(rows)} validated rows")
    import bq as BQ
    res = BQ.write_snapshot("competitor", [r.to_bq() for r in rows], C.RUN_ID)
    print(f"[competitor][BQ] {res}")


if __name__ == "__main__":
    main()
