"""Pydantic validation contract for the Job Market Demand tab (LinkedIn).

This schema IS the orchestrator's tool-call gate: every scraped + normalized row
must validate here before it is accepted into BigQuery. Adapted from the v0.1
plan's `JobDemand` to LinkedIn's real fields:
  - salary_min/max are OPTIONAL (LinkedIn India almost never exposes salary);
  - added LinkedIn-native signal: seniority, employment type, job function,
    industries, applicants count;
  - added run_date (monthly snapshot / partition key) so YoY / MoM demand is a
    query over the table rather than a per-row guess.
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator

# BigQuery column schema, kept in lockstep with the model below.
BQ_SCHEMA = [
    ("run_id", "STRING", "REQUIRED"),
    ("run_date", "DATE", "REQUIRED"),
    ("scraped_at", "TIMESTAMP", "REQUIRED"),
    ("source", "STRING", "REQUIRED"),
    ("query", "STRING", "NULLABLE"),
    ("job_id", "STRING", "NULLABLE"),
    ("title", "STRING", "REQUIRED"),
    ("normalized_role", "STRING", "NULLABLE"),
    ("role_family", "STRING", "NULLABLE"),
    ("company", "STRING", "NULLABLE"),
    ("company_tier", "STRING", "NULLABLE"),
    ("location", "STRING", "NULLABLE"),
    ("seniority_level", "STRING", "NULLABLE"),
    ("employment_type", "STRING", "NULLABLE"),
    ("job_function", "STRING", "NULLABLE"),
    ("industries", "STRING", "NULLABLE"),
    ("applicants_count", "INTEGER", "NULLABLE"),
    ("salary_raw", "STRING", "NULLABLE"),
    ("salary_min_inr", "INTEGER", "NULLABLE"),
    ("salary_max_inr", "INTEGER", "NULLABLE"),
    ("posted_date", "DATE", "NULLABLE"),
    ("posted_raw", "STRING", "NULLABLE"),
    ("in_window", "BOOLEAN", "NULLABLE"),
    ("emerging_bucket", "STRING", "NULLABLE"),
    ("seniority_bucket", "STRING", "NULLABLE"),
    ("canonical_bucket", "STRING", "NULLABLE"),
    ("is_emerging", "BOOLEAN", "NULLABLE"),
    ("lenses", "STRING", "REPEATED"),
    ("skills", "STRING", "REPEATED"),
    ("reference_url", "STRING", "NULLABLE"),
]


class JobDemandRow(BaseModel):
    # provenance / partition
    run_id: str
    run_date: date
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: Literal["LinkedIn", "Naukri"] = "LinkedIn"
    query: Optional[str] = None
    job_id: Optional[str] = None

    # core
    title: str
    normalized_role: Optional[str] = None
    role_family: Optional[str] = None
    company: Optional[str] = None
    company_tier: Optional[str] = None
    location: Optional[str] = None

    # LinkedIn-native signal
    seniority_level: Optional[str] = None
    employment_type: Optional[str] = None
    job_function: Optional[str] = None
    industries: Optional[str] = None
    applicants_count: Optional[int] = Field(default=None, ge=0)

    # compensation (opportunistic; usually null on LinkedIn India)
    salary_raw: Optional[str] = None
    salary_min_inr: Optional[int] = Field(default=None, ge=0)
    salary_max_inr: Optional[int] = Field(default=None, ge=0)

    # recency
    posted_date: Optional[date] = None
    posted_raw: Optional[str] = None
    in_window: Optional[bool] = None

    # emerging-role scoring
    emerging_bucket: Optional[str] = None
    seniority_bucket: Optional[str] = None
    canonical_bucket: Optional[str] = None
    is_emerging: bool = False
    lenses: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)

    reference_url: Optional[str] = None

    @field_validator("title")
    @classmethod
    def _title_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("title must be non-empty")
        return v.strip()

    def to_bq(self) -> dict:
        """JSON-serializable dict matching BQ_SCHEMA (dates/datetimes as ISO)."""
        d = self.model_dump()
        d["run_date"] = self.run_date.isoformat()
        d["scraped_at"] = self.scraped_at.isoformat()
        d["posted_date"] = self.posted_date.isoformat() if self.posted_date else None
        return d
