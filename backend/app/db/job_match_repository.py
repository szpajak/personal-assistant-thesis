"""Postgres repository for persisted job match scores."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.job_match import JobMatch


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class JobMatchRepository:
    """CRUD for the ``job_matches`` cache table."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, person_id: str, job_id: str) -> JobMatch | None:
        result = await self.db.execute(
            select(JobMatch).where(
                JobMatch.person_id == person_id,
                JobMatch.job_id == job_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_person(self, person_id: str) -> list[JobMatch]:
        result = await self.db.execute(
            select(JobMatch)
            .where(JobMatch.person_id == person_id)
            .order_by(JobMatch.match_score.desc(), JobMatch.matched_at.desc())
        )
        return list(result.scalars().all())

    async def upsert(
        self,
        *,
        person_id: str,
        job_id: str,
        job_tier: str,
        match_score: int,
        quick_score: int,
        matching_skills: list[str],
        missing_skills: list[str],
        justification: str,
        source: str,
        profile_fingerprint: str,
    ) -> JobMatch:
        existing = await self.get(person_id, job_id)
        now = _utc_now_naive()
        if existing:
            existing.job_tier = job_tier
            existing.match_score = match_score
            existing.quick_score = quick_score
            existing.matching_skills = list(matching_skills)
            existing.missing_skills = list(missing_skills)
            existing.justification = justification
            existing.source = source
            existing.profile_fingerprint = profile_fingerprint
            existing.matched_at = now
            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        row = JobMatch(
            id=str(uuid.uuid4()),
            person_id=person_id,
            job_id=job_id,
            job_tier=job_tier,
            match_score=match_score,
            quick_score=quick_score,
            matching_skills=list(matching_skills),
            missing_skills=list(missing_skills),
            justification=justification,
            source=source,
            profile_fingerprint=profile_fingerprint,
            matched_at=now,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    def to_dict(self, row: JobMatch) -> dict[str, Any]:
        return {
            "id": row.id,
            "person_id": row.person_id,
            "job_id": row.job_id,
            "job_tier": row.job_tier,
            "match_score": row.match_score,
            "quick_score": row.quick_score,
            "matching_skills": list(row.matching_skills or []),
            "missing_skills": list(row.missing_skills or []),
            "justification": row.justification or "",
            "source": row.source,
            "profile_fingerprint": row.profile_fingerprint,
            "matched_at": row.matched_at,
        }
