"""Celery task: sample real job postings for a TargetRole.

Scrapes ~50 unique offers for the role's title/location, ingests them into
Neo4j as ``JobOffer`` nodes with ``purpose='market_sample'``, and links them
via ``(TargetRole)-[:SAMPLED]->(JobOffer)`` so skill-gap analysis and
GraphRAG retrieval for that role are grounded in real market data instead of
a best-match over an arbitrary title. See the "Skills tab redesign" plan.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from ..core.celery_app import celery_app
from ..core.database import celery_db_session
from ..db.job_listing_repository import JobListingRepository, listing_to_dict
from ..kg.embeddings import KGEmbeddings
from ..kg.ingestion import KGIngestion
from ..kg.repository import KGRepository
from ..schemas.job_scraping import JobScrapeRequest
from ..services.job_scraper_service import JobScraperService

logger = logging.getLogger(__name__)

# Target total postings across all default sites (linkedin + indeed) - the
# "~50 offers" the plan calls for. results_wanted on JobScrapeRequest is
# per-site, so this is split evenly across whatever sites are configured.
_SAMPLE_TARGET_TOTAL = 50


async def _mark_status(repo: KGRepository, role_id: str, status: str) -> None:
    await repo.upsert_node("TargetRole", {"id": role_id, "sample_status": status})


async def _run_refresh(role_id: str) -> dict[str, object]:
    async with celery_db_session() as session:
        repo = KGRepository()
        embeddings = KGEmbeddings(kg_repository=repo)
        ingestion = KGIngestion(kg_repository=repo, embeddings=embeddings)
        listing_repo = JobListingRepository(db=session)

        role = await repo.get_node("TargetRole", role_id)
        if not role:
            logger.warning("Target role %s not found, aborting sample refresh", role_id)
            return {"status": "error", "reason": "not_found"}

        title = str(role.get("title") or "").strip()
        location = str(role.get("location") or "").strip()
        country = str(role.get("country") or "").strip()
        if not title:
            await _mark_status(repo, role_id, "error")
            return {"status": "error", "reason": "missing_title"}

        await _mark_status(repo, role_id, "scraping")

        sites = JobScraperService.filters_from_request(None).sites
        per_site = max(1, -(-_SAMPLE_TARGET_TOTAL // max(1, len(sites))))
        request = JobScrapeRequest(
            search_term=title,
            location=location or None,
            country=country or None,
            results_wanted=min(50, per_site),
        )

        scraper = JobScraperService(job_listing_repository=listing_repo, kg_repository=repo)
        try:
            await scraper.scrape_job_boards(request=request)
        except Exception as exc:
            logger.error("Role sample scrape failed for %s: %s", role_id, exc)
            await _mark_status(repo, role_id, "error")
            return {"status": "error", "reason": "scrape_failed"}

        listings = await listing_repo.list_by_search_term(title, limit=_SAMPLE_TARGET_TOTAL)
        if not listings:
            logger.warning("No offers scraped for target role %s ('%s')", role_id, title)
            await _mark_status(repo, role_id, "error")
            return {"status": "error", "reason": "no_results"}

        await _mark_status(repo, role_id, "ingesting")

        job_ids: list[str] = []
        for listing_row in listings[:_SAMPLE_TARGET_TOTAL]:
            try:
                job_id = await ingestion.ingest_market_sample_job(
                    job_id=str(listing_row.id),
                    listing=listing_to_dict(listing_row),
                )
                job_ids.append(job_id)
            except Exception as exc:
                logger.warning("Failed to ingest sample job %s: %s", listing_row.id, exc)

        if not job_ids:
            await _mark_status(repo, role_id, "error")
            return {"status": "error", "reason": "ingest_failed"}

        await ingestion.replace_target_role_sample(role_id, job_ids)

        stats = await repo.get_target_role_sample_stats(role_id)
        top_skills = [str(row["name"]) for row in stats[:15] if row.get("name")]
        await ingestion.set_target_role_required_skills(role_id, top_skills)

        await repo.upsert_node(
            "TargetRole",
            {
                "id": role_id,
                "sample_status": "ready",
                "sample_job_count": len(job_ids),
                "last_sampled_at": datetime.now(UTC).isoformat(),
            },
        )
        return {"status": "ready", "count": len(job_ids)}


@celery_app.task  # type: ignore[untyped-decorator]
def refresh_target_role_sample(role_id: str) -> dict[str, object]:
    """Scrape + ingest a fresh market sample for ``role_id`` (see module docstring)."""
    try:
        return asyncio.run(_run_refresh(role_id))
    except Exception as e:
        logger.error("Target role sample refresh failed for %s: %s", role_id, e)
        try:
            asyncio.run(_mark_status(KGRepository(), role_id, "error"))
        except Exception:
            pass
        raise
