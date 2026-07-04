"""Pydantic validation contracts + BigQuery schemas for every tab.

Each model is the orchestrator's tool-call gate: a worker's output row must
validate here before it is written. Columns mirror the reference workbook tabs
(Reference/*.csv) plus provenance (run_id/run_date) for trend snapshots.
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator


def _now():
    return datetime.now(timezone.utc)


class Provenance(BaseModel):
    run_id: str
    run_date: date
    scraped_at: datetime = Field(default_factory=_now)
    source: Optional[str] = None

    def to_bq(self) -> dict:
        d = self.model_dump()
        for k, v in list(d.items()):
            if isinstance(v, datetime):
                d[k] = v.isoformat()
            elif isinstance(v, date):
                d[k] = v.isoformat()
        return d


# ---- Tab 1: Social Media Trends ------------------------------------------
class SocialTrendRow(Provenance):
    topic: str                                   # Trending Topic/Keyword
    sentiment: int = Field(ge=1, le=5)           # Sentiment Score x/5
    engagement: str                              # Engagement Volume ("122,000 stars")
    engagement_value: Optional[int] = None       # numeric parse for ranking
    category: Optional[str] = None               # framework / model / infra / paper / discussion
    reference_url: str

    @field_validator("topic")
    @classmethod
    def _t(cls, v):
        if not v or not v.strip(): raise ValueError("topic empty")
        return v.strip()


SOCIAL_BQ = [
    ("run_id","STRING","REQUIRED"),("run_date","DATE","REQUIRED"),("scraped_at","TIMESTAMP","REQUIRED"),
    ("source","STRING","NULLABLE"),("topic","STRING","REQUIRED"),("sentiment","INTEGER","NULLABLE"),
    ("engagement","STRING","NULLABLE"),("engagement_value","INTEGER","NULLABLE"),
    ("category","STRING","NULLABLE"),("reference_url","STRING","NULLABLE"),
]


# ---- Tab 2: Blog & Publications ------------------------------------------
class BlogRow(Provenance):
    publication: str
    title: str
    recommended_skill: str
    audience: str                                # Fresher / Working Pro / Manager / ...
    urgency: Literal["Must-have NOW", "High priority", "Future trend"]
    curriculum_match: Literal["Yes", "Partial", "No - GAP", "N/A"]
    published_date: Optional[date] = None
    summary: Optional[str] = None
    reference_url: str


BLOG_BQ = [
    ("run_id","STRING","REQUIRED"),("run_date","DATE","REQUIRED"),("scraped_at","TIMESTAMP","REQUIRED"),
    ("source","STRING","NULLABLE"),("publication","STRING","NULLABLE"),("title","STRING","REQUIRED"),
    ("recommended_skill","STRING","NULLABLE"),("audience","STRING","NULLABLE"),("urgency","STRING","NULLABLE"),
    ("curriculum_match","STRING","NULLABLE"),("published_date","DATE","NULLABLE"),
    ("summary","STRING","NULLABLE"),("reference_url","STRING","NULLABLE"),
]


# ---- Tab 4: Competitor Intelligence (14-col battlecard) ------------------
class CompetitorRow(Provenance):
    competitor: str
    program: str
    price_inr: Optional[int] = Field(default=None, ge=0)
    price_source: Optional[str] = None           # Jina/DOM | Shiksha | Wayback | ...
    confidence: Literal["high", "medium", "low"] = "medium"
    duration_months: Optional[int] = Field(default=None, ge=0)
    curriculum_overview: Optional[str] = None
    key_tools: list[str] = Field(default_factory=list)
    hands_on_projects: Optional[str] = None
    certifications: Optional[str] = None
    mentor_quality: Optional[str] = None
    curriculum_gaps_vs_ik: list[str] = Field(default_factory=list)
    ik_advantages: list[str] = Field(default_factory=list)
    ik_gaps: list[str] = Field(default_factory=list)
    ad_intensity: int = Field(default=3, ge=1, le=5)
    reference_url: str


COMPETITOR_BQ = [
    ("run_id","STRING","REQUIRED"),("run_date","DATE","REQUIRED"),("scraped_at","TIMESTAMP","REQUIRED"),
    ("source","STRING","NULLABLE"),("competitor","STRING","REQUIRED"),("program","STRING","NULLABLE"),
    ("price_inr","INTEGER","NULLABLE"),("price_source","STRING","NULLABLE"),("confidence","STRING","NULLABLE"),
    ("duration_months","INTEGER","NULLABLE"),("curriculum_overview","STRING","NULLABLE"),
    ("key_tools","STRING","REPEATED"),("hands_on_projects","STRING","NULLABLE"),
    ("certifications","STRING","NULLABLE"),("mentor_quality","STRING","NULLABLE"),
    ("curriculum_gaps_vs_ik","STRING","REPEATED"),("ik_advantages","STRING","REPEATED"),
    ("ik_gaps","STRING","REPEATED"),("ad_intensity","INTEGER","NULLABLE"),("reference_url","STRING","NULLABLE"),
]


# ---- Executive Summary: one ranked priority ------------------------------
class ExecPriorityRow(Provenance):
    rank: int = Field(ge=1)
    direction: str
    sections: list[str] = Field(default_factory=list)   # which tabs flagged it
    urgency: Literal["CRITICAL", "HIGH", "MEDIUM"]
    gap_vs_competitors: Optional[str] = None
    actionable_insight: str
    effort_estimate: Optional[str] = None
    revenue_impact: Optional[str] = None
    supporting_data: Optional[str] = None


EXEC_BQ = [
    ("run_id","STRING","REQUIRED"),("run_date","DATE","REQUIRED"),("scraped_at","TIMESTAMP","REQUIRED"),
    ("source","STRING","NULLABLE"),("rank","INTEGER","REQUIRED"),("direction","STRING","NULLABLE"),
    ("sections","STRING","REPEATED"),("urgency","STRING","NULLABLE"),("gap_vs_competitors","STRING","NULLABLE"),
    ("actionable_insight","STRING","NULLABLE"),("effort_estimate","STRING","NULLABLE"),
    ("revenue_impact","STRING","NULLABLE"),("supporting_data","STRING","NULLABLE"),
]


# tab key -> (model, bq schema)
REGISTRY = {
    "social":     (SocialTrendRow, SOCIAL_BQ),
    "blog":       (BlogRow,        BLOG_BQ),
    "competitor": (CompetitorRow,  COMPETITOR_BQ),
    "exec":       (ExecPriorityRow, EXEC_BQ),
}
