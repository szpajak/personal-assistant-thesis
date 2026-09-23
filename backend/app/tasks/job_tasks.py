"""Celery background tasks for job processing."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..core.celery_app import celery_app
from ..core.database import celery_db_session
from ..db.job_listing_repository import JobListingRepository
from ..kg.repository import KGRepository
from ..schemas.job_scraping import JobScrapeRequest
from ..services.job_scraper_service import JobScraperService

logger = logging.getLogger(__name__)


@celery_app.task  # type: ignore[untyped-decorator]
def scrape_job_offers(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Scrape job boards into the Postgres staging table.

    Staging writes never create embeddings or REQUIRES edges — those run
    only on promote. Known Skill names may be read from Neo4j so the
    heuristic extractor can persist required_skills for overlap matching.
    """

    async def _run() -> dict[str, Any]:
        # Per-task engine: Celery's asyncio.run() creates a new event loop each
        # invocation; a module-level asyncpg pool from a prior loop will crash.
        async with celery_db_session() as session:
            service = JobScraperService(
                job_listing_repository=JobListingRepository(db=session),
                kg_repository=KGRepository(),
            )
            request = JobScrapeRequest.model_validate(filters) if filters else None
            result = await service.scrape_job_boards(request=request)
            return result.stats.to_dict()

    try:
        stats = asyncio.run(_run())
        logger.info("Job scraping task completed: %s", stats)
        return stats
    except Exception as e:
        logger.error(f"Job scraping task failed: {e}")
        raise
