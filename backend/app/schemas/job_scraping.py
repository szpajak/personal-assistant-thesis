from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class UpsertAction(str, Enum):
    INGESTED = "ingested"
    UPDATED = "updated"
    SKIPPED = "skipped"


JobTypeFilter = Literal["fulltime", "parttime", "internship", "contract"]


@dataclass
class ScrapedJob:
    external_id: str
    title: str
    company: str
    description: str
    url: str
    location: str
    source: str
    search_term: str
    job_type: str | None = None
    salary_range: str | None = None
    posted_at: str | None = None


@dataclass
class JobScrapeStats:
    ingested: int = 0
    updated: int = 0
    skipped: int = 0
    expired: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "ingested": self.ingested,
            "updated": self.updated,
            "skipped": self.skipped,
            "expired": self.expired,
        }


@dataclass
class JobScrapeRunResult:
    stats: JobScrapeStats = field(default_factory=JobScrapeStats)
    job_ids: list[str] = field(default_factory=list)


class JobScrapeRequest(BaseModel):
    """Filters forwarded to jobspy2 ``scrape_jobs`` for an on-demand search."""

    search_term: str = Field(..., min_length=1, description="Job title / keywords")
    location: str | None = Field(
        default=None,
        description="City, region, or country string (e.g. 'Warsaw, Poland')",
    )
    country: str | None = Field(
        default=None,
        description="Indeed/Glassdoor country (e.g. 'Poland', 'USA', 'UK', 'Germany')",
    )
    sites: list[str] | None = Field(
        default=None,
        description="Job boards to scrape (linkedin, indeed, glassdoor, zip_recruiter, google)",
    )
    job_type: JobTypeFilter | None = Field(
        default=None,
        description="Employment type filter supported by jobspy2",
    )
    is_remote: bool = Field(default=False, description="Prefer remote listings")
    hours_old: int | None = Field(
        default=None,
        ge=1,
        description="Only jobs posted within the last N hours",
    )
    distance: int | None = Field(
        default=None,
        ge=1,
        description="Search radius in miles around location",
    )
    results_wanted: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description="Max results to fetch per site (capped for rate limiting)",
    )
    include_remoteok: bool = Field(
        default=False,
        description="Also pull the unfiltered RemoteOK feed",
    )


class JobScrapeTaskResponse(BaseModel):
    task_id: str
    message: str


class JobScrapeStatsResponse(BaseModel):
    ingested: int
    updated: int
    skipped: int
    expired: int
