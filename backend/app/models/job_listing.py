from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text

from app.models.base import Base


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ScrapedJobListing(Base):
    """A scraped-but-not-promoted job offer.

    Lives outside the knowledge graph entirely so the graph only holds
    ``JobOffer`` nodes the user deliberately promoted/saved. A row is deleted
    the moment it's promoted (see ``KGIngestion.promote_job``) so a given job
    never exists in both stores at once.
    """

    __tablename__ = "scraped_job_listings"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    description = Column(Text, nullable=False, default="")
    url = Column(String, nullable=False, unique=True, index=True)
    location = Column(String, nullable=True)
    source = Column(String, nullable=True, index=True)
    external_id = Column(String, nullable=True)
    search_term = Column(String, nullable=True)
    job_type = Column(String, nullable=True)
    salary_range = Column(String, nullable=True)
    posted_at = Column(String, nullable=True)
    required_skills = Column(JSON, nullable=False, default=list)
    seniority = Column(String, nullable=True, index=True)
    min_experience_years = Column(Integer, nullable=True)
    max_experience_years = Column(Integer, nullable=True)
    # Naive UTC to match Postgres TIMESTAMP WITHOUT TIME ZONE
    scraped_at = Column(DateTime, default=_utc_now_naive, nullable=False)
    status = Column(String, nullable=False, default="active", index=True)
