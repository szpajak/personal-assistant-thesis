"""Postgres repository for scraped (not-yet-promoted) job listings.

Deliberately separate from ``app/kg/repository.py`` - these rows never touch
Neo4j. Once a listing is promoted (``KGIngestion.promote_job``) its row here
is deleted, so a job never exists in both stores at the same time.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.job_listing import ScrapedJobListing
from ..schemas.job_scraping import UpsertAction
from ..utils.job_url import normalize_job_url

DEFAULT_LIST_LIMIT = 100


def _utc_now_naive() -> datetime:
    """UTC timestamp without tzinfo — matches ``TIMESTAMP WITHOUT TIME ZONE``."""
    return datetime.now(UTC).replace(tzinfo=None)


def _as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _resolve_url(metadata: dict[str, Any]) -> str:
    url = metadata.get("url", "")
    if url:
        return normalize_job_url(str(url)) or str(url)
    source = metadata.get("source", "unknown")
    external_id = metadata.get("external_id", str(uuid.uuid4()))
    return f"{source}://job/{external_id}"


def listing_to_dict(listing: ScrapedJobListing) -> dict[str, Any]:
    """Adapt a ``ScrapedJobListing`` ORM row into the plain dict shape the
    rest of the job pipeline (``KGIngestion``, matching, ``JobService``)
    already expects from Neo4j node properties.
    """
    return {
        "id": listing.id,
        "title": listing.title,
        "company": listing.company,
        "description": listing.description,
        "required_skills": listing.required_skills or [],
        "url": listing.url,
        "location": listing.location,
        "salary_range": listing.salary_range,
        "source": listing.source,
        "external_id": listing.external_id,
        "scraped_at": listing.scraped_at,
        "posted_at": listing.posted_at,
        "status": listing.status,
        "job_type": listing.job_type,
        "search_term": listing.search_term,
        "seniority": listing.seniority,
        "min_experience_years": listing.min_experience_years,
        "max_experience_years": listing.max_experience_years,
    }


class JobListingRepository:
    """CRUD + filtering for the ``scraped_job_listings`` table."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, listing_id: str) -> ScrapedJobListing | None:
        result = await self.db.execute(
            select(ScrapedJobListing).where(ScrapedJobListing.id == listing_id)
        )
        return result.scalar_one_or_none()

    async def get_by_url(self, url: str) -> ScrapedJobListing | None:
        normalized = normalize_job_url(url) or url
        result = await self.db.execute(
            select(ScrapedJobListing).where(ScrapedJobListing.url == normalized)
        )
        return result.scalar_one_or_none()

    async def get_by_source_external_id(
        self, source: str, external_id: str
    ) -> ScrapedJobListing | None:
        if not source or not external_id:
            return None
        result = await self.db.execute(
            select(ScrapedJobListing).where(
                ScrapedJobListing.source == source,
                ScrapedJobListing.external_id == external_id,
            )
        )
        return result.scalar_one_or_none()

    def _is_fresh(self, scraped_at: datetime | None, ttl_days: int) -> bool:
        if not scraped_at:
            return False
        reference = _as_naive_utc(scraped_at)
        return _utc_now_naive() - reference < timedelta(days=ttl_days)

    async def upsert_by_url(
        self,
        title: str,
        company: str,
        description: str,
        required_skills: list[str],
        metadata: dict[str, Any],
        ttl_days: int = 7,
        seniority: str | None = None,
        min_experience_years: int | None = None,
        max_experience_years: int | None = None,
    ) -> tuple[UpsertAction, str]:
        """Upsert a scraped listing by normalized URL (or source+external_id)."""
        url = _resolve_url(metadata)
        source = str(metadata.get("source") or "")
        external_id = str(metadata.get("external_id") or "")

        existing = await self.get_by_url(url)
        if existing is None and source and external_id:
            existing = await self.get_by_source_external_id(source, external_id)

        now = _utc_now_naive()

        if existing and self._is_fresh(existing.scraped_at, ttl_days):
            if existing.description == description and (
                existing.required_skills or []
            ) == list(required_skills):
                return UpsertAction.SKIPPED, str(existing.id)

        listing_id = str(existing.id) if existing else str(uuid.uuid4())
        action = UpsertAction.UPDATED if existing else UpsertAction.INGESTED

        values = {
            "title": title,
            "company": company,
            "description": description,
            "required_skills": list(required_skills),
            "url": url,
            "salary_range": metadata.get("salary_range"),
            "location": metadata.get("location", ""),
            "source": source,
            "external_id": external_id,
            "scraped_at": now,
            "posted_at": metadata.get("posted_at"),
            "status": "active",
            "job_type": metadata.get("job_type"),
            "search_term": metadata.get("search_term"),
            "seniority": seniority,
            "min_experience_years": min_experience_years,
            "max_experience_years": max_experience_years,
        }

        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
        else:
            self.db.add(ScrapedJobListing(id=listing_id, **values))

        await self.db.commit()
        return action, listing_id

    async def list_listings(
        self,
        search: str | None = None,
        source: str | None = None,
        seniority: str | None = None,
        min_years: int | None = None,
        max_years: int | None = None,
        status: str | None = "active",
        limit: int = DEFAULT_LIST_LIMIT,
    ) -> list[ScrapedJobListing]:
        query = select(ScrapedJobListing)

        if status:
            query = query.where(ScrapedJobListing.status == status)
        if source:
            query = query.where(ScrapedJobListing.source == source)
        if seniority:
            query = query.where(ScrapedJobListing.seniority == seniority)
        if search:
            like = f"%{search.lower()}%"
            query = query.where(
                or_(
                    ScrapedJobListing.title.ilike(like),
                    ScrapedJobListing.company.ilike(like),
                )
            )
        if min_years is not None:
            # A listing's own experience *requirement* range must overlap
            # the requested bracket - unknown (NULL) upper bound means "no
            # stated ceiling", which always overlaps an upper-bounded query.
            query = query.where(
                or_(
                    ScrapedJobListing.max_experience_years.is_(None),
                    ScrapedJobListing.max_experience_years >= min_years,
                )
            )
        if max_years is not None:
            query = query.where(
                or_(
                    ScrapedJobListing.min_experience_years.is_(None),
                    ScrapedJobListing.min_experience_years <= max_years,
                )
            )

        query = query.order_by(ScrapedJobListing.scraped_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_by_search_term(
        self, search_term: str, limit: int = DEFAULT_LIST_LIMIT
    ) -> list[ScrapedJobListing]:
        """Return listings from the most recent scrape(s) for an exact
        ``search_term`` (the raw title string a scrape was run with) -
        used by TargetRole sampling to pull back exactly the postings a
        role refresh just fetched, regardless of ``status``/TTL.
        """
        result = await self.db.execute(
            select(ScrapedJobListing)
            .where(ScrapedJobListing.search_term == search_term)
            .order_by(ScrapedJobListing.scraped_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_by_id(self, listing_id: str) -> bool:
        listing = await self.get_by_id(listing_id)
        if not listing:
            return False
        await self.db.delete(listing)
        await self.db.commit()
        return True

    async def delete_by_url(self, url: str) -> None:
        await self.db.execute(
            delete(ScrapedJobListing).where(ScrapedJobListing.url == url)
        )
        await self.db.commit()

    async def expire_stale(
        self,
        source: str,
        seen_urls: list[str],
        ttl_days: int,
    ) -> int:
        """Mark listings from ``source`` not seen in the latest scrape as
        expired once they're older than ``ttl_days`` (soft-delete; the user
        can still see/delete them manually via the Scraped Offers tab).
        """
        cutoff = _utc_now_naive() - timedelta(days=ttl_days)
        query = select(ScrapedJobListing).where(
            ScrapedJobListing.source == source,
            ScrapedJobListing.status == "active",
            ScrapedJobListing.scraped_at < cutoff,
        )
        if seen_urls:
            query = query.where(ScrapedJobListing.url.notin_(seen_urls))

        result = await self.db.execute(query)
        stale = list(result.scalars().all())
        for listing in stale:
            listing.status = "expired"
        if stale:
            await self.db.commit()
        return len(stale)
