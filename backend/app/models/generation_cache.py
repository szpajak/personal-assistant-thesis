"""Cached LLM generation artifacts (CV text, skill analysis JSON)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, String, Text, UniqueConstraint

from app.models.base import Base


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class GenerationCache(Base):
    """Store expensive generation outputs keyed by person + kind + subject."""

    __tablename__ = "generation_cache"
    __table_args__ = (
        UniqueConstraint(
            "person_id",
            "kind",
            "subject_id",
            name="uq_generation_cache_person_kind_subject",
        ),
    )

    id = Column(String, primary_key=True)
    person_id = Column(String, nullable=False, index=True)
    kind = Column(String, nullable=False)  # cv | skill_analysis | suggested_projects
    subject_id = Column(String, nullable=False, default="default")
    profile_fingerprint = Column(String, nullable=False, default="")
    payload_text = Column(Text, nullable=True)
    payload_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_utc_now_naive, nullable=False)
