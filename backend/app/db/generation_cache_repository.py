"""Postgres repository for CV / skill-analysis generation cache."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.generation_cache import GenerationCache


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class GenerationCacheRepository:
    """CRUD for the ``generation_cache`` table."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(
        self,
        person_id: str,
        kind: str,
        subject_id: str,
    ) -> GenerationCache | None:
        result = await self.db.execute(
            select(GenerationCache).where(
                GenerationCache.person_id == person_id,
                GenerationCache.kind == kind,
                GenerationCache.subject_id == subject_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_valid(
        self,
        person_id: str,
        kind: str,
        subject_id: str,
        fingerprint: str,
    ) -> GenerationCache | None:
        row = await self.get(person_id, kind, subject_id)
        if row is None:
            return None
        if row.profile_fingerprint != fingerprint:
            return None
        return row

    async def upsert(
        self,
        *,
        person_id: str,
        kind: str,
        subject_id: str,
        profile_fingerprint: str,
        payload_text: str | None = None,
        payload_json: dict[str, Any] | list[Any] | None = None,
    ) -> GenerationCache:
        existing = await self.get(person_id, kind, subject_id)
        now = _utc_now_naive()
        if existing:
            existing.profile_fingerprint = profile_fingerprint
            existing.payload_text = payload_text
            existing.payload_json = payload_json
            existing.created_at = now
            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        row = GenerationCache(
            id=str(uuid.uuid4()),
            person_id=person_id,
            kind=kind,
            subject_id=subject_id,
            profile_fingerprint=profile_fingerprint,
            payload_text=payload_text,
            payload_json=payload_json,
            created_at=now,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row
