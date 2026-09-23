"""Persisted job-match scores (LLM or quick overlap)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, UniqueConstraint

from app.models.base import Base


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class JobMatch(Base):
    """Cached match between a person and a job (staging listing or career offer)."""

    __tablename__ = "job_matches"
    __table_args__ = (
        UniqueConstraint("person_id", "job_id", name="uq_job_matches_person_job"),
    )

    id = Column(String, primary_key=True)
    person_id = Column(String, nullable=False, index=True)
    job_id = Column(String, nullable=False, index=True)
    job_tier = Column(String, nullable=False, default="career")  # staging | career
    match_score = Column(Integer, nullable=False, default=0)
    quick_score = Column(Integer, nullable=False, default=0)
    matching_skills = Column(JSON, nullable=False, default=list)
    missing_skills = Column(JSON, nullable=False, default=list)
    justification = Column(String, nullable=False, default="")
    source = Column(String, nullable=False, default="overlap")  # overlap | llm
    profile_fingerprint = Column(String, nullable=False, default="")
    matched_at = Column(DateTime, default=_utc_now_naive, nullable=False)
