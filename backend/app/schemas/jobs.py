from __future__ import annotations

from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, Field

JobTier = Literal["staging", "career"]
MatchSource = Literal["overlap", "llm", "none"]


class JobOfferRead(BaseModel):
    id: str
    title: str
    company: str
    url: str
    description: str
    required_skills: List[str]
    scraped_at: datetime
    # staging = scraped listing (Postgres); career = promoted JobOffer in the KG
    tier: JobTier = "career"
    location: str = ""
    salary_range: str | None = None
    job_type: str | None = None
    source: str | None = None
    seniority: str | None = None
    min_experience_years: int | None = None
    max_experience_years: int | None = None


class JobMatchResponse(BaseModel):
    job_offer: JobOfferRead
    score: float
    matching_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    justification: str = ""
    quick_score: float = 0.0
    is_stale: bool = False
    matched_at: datetime | None = None
    source: MatchSource = "none"


class JobMatchBatchRequest(BaseModel):
    """Empty / omitted ``job_ids`` means all active career offers (capped)."""

    job_ids: list[str] | None = Field(
        default=None,
        description="Explicit job ids to LLM-match. Null/empty = all active career offers.",
    )


class JobPromoteResponse(BaseModel):
    job_offer: JobOfferRead
    promoted: bool = Field(
        description="True when a staging listing was newly promoted; False if already career"
    )
