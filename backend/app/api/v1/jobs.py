from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...core.celery_app import celery_app
from ...db.job_listing_repository import JobListingRepository
from ...db.job_match_repository import JobMatchRepository
from ...dependencies import get_current_user, get_db_session
from ...kg.embeddings import KGEmbeddings
from ...kg.ingestion import KGIngestion
from ...kg.repository import KGRepository
from ...models.user import User
from ...pipelines.job_match_pipeline import JobMatchPipeline
from ...schemas.job_scraping import JobScrapeRequest, JobScrapeTaskResponse
from ...schemas.jobs import (
    JobMatchBatchRequest,
    JobMatchResponse,
    JobOfferRead,
    JobPromoteResponse,
)
from ...services.job_service import JobService, MatchBudgetExceeded

router = APIRouter()

_EXPERIENCE_BRACKETS = {
    "0-2": (0, 2),
    "2-5": (2, 5),
    "5+": (5, None),
}


def get_job_service(
    repo: KGRepository = Depends(),
    db: AsyncSession = Depends(get_db_session),
) -> JobService:
    embeddings = KGEmbeddings(kg_repository=repo)
    job_listing_repository = JobListingRepository(db=db)
    job_match_repository = JobMatchRepository(db=db)
    pipeline = JobMatchPipeline(
        kg_repository=repo,
        job_listing_repository=job_listing_repository,
        embeddings=embeddings,
    )
    ingestion = KGIngestion(
        kg_repository=repo,
        embeddings=embeddings,
        scrape_ttl_days=settings.job_scrape_ttl_days,
    )
    return JobService(
        kg_repository=repo,
        job_match_pipeline=pipeline,
        job_listing_repository=job_listing_repository,
        job_match_repository=job_match_repository,
        kg_ingestion=ingestion,
    )


@router.get("/", response_model=list[JobOfferRead])
async def list_jobs(
    source: str | None = Query(default=None),
    status: str | None = Query(default="active"),
    search: str | None = Query(default=None),
    tier: str | None = Query(
        default="all",
        description="staging | career | all",
    ),
    current_user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> list[JobOfferRead]:
    resolved_tier = tier if tier in {"staging", "career", "all"} else "all"
    offers: list[JobOfferRead] = await service.list_offers(
        source=source,
        status=status,
        search=search,
        tier=resolved_tier,  # type: ignore[arg-type]
    )
    return offers


@router.get("/match", response_model=list[JobMatchResponse])
async def list_job_matches(
    current_user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> list[JobMatchResponse]:
    """Return cached matches + live quick overlap scores for career and
    staging jobs. Never calls the LLM."""
    person_id = f"user_{current_user.id}"
    return await service.list_cached_matches(person_id)


@router.post("/match", response_model=list[JobMatchResponse])
async def match_jobs_batch(
    body: JobMatchBatchRequest,
    current_user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> list[JobMatchResponse]:
    """LLM-match selected jobs, or all active career offers when job_ids is empty."""
    person_id = f"user_{current_user.id}"
    try:
        return await service.match_batch(person_id, body.job_ids)
    except MatchBudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


@router.post("/scrape", response_model=JobScrapeTaskResponse)
async def trigger_job_scrape(
    body: JobScrapeRequest,
    current_user: User = Depends(get_current_user),
) -> JobScrapeTaskResponse:
    """Queue a background scrape into staging JobListing nodes."""
    task = celery_app.send_task(
        "app.tasks.job_tasks.scrape_job_offers",
        kwargs={"filters": body.model_dump(mode="json")},
    )
    return JobScrapeTaskResponse(
        task_id=task.id,
        message="Job scraping task queued",
    )


@router.get("/scraped", response_model=list[JobOfferRead])
async def list_scraped_jobs(
    search: str | None = Query(default=None),
    source: str | None = Query(default=None),
    status: str | None = Query(default="active"),
    seniority: str | None = Query(default=None, description="junior | mid | senior"),
    experience_bracket: str | None = Query(default=None, description="0-2 | 2-5 | 5+"),
    current_user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> list[JobOfferRead]:
    """List scraped-but-not-promoted listings (Postgres) for the Scraped Offers tab."""
    min_years, max_years = _EXPERIENCE_BRACKETS.get(
        experience_bracket or "", (None, None)
    )
    return await service.list_scraped(
        search=search,
        source=source,
        status=status,
        seniority=seniority,
        min_years=min_years,
        max_years=max_years,
    )


@router.delete("/scraped/{listing_id}", status_code=204, response_class=Response)
async def delete_scraped_job(
    listing_id: str,
    current_user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> Response:
    """Delete a scraped listing to reclaim storage / clean up unwanted entries."""
    deleted = await service.delete_scraped(listing_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Scraped listing {listing_id} not found"
        )
    return Response(status_code=204)


@router.post("/{job_id}/match", response_model=JobMatchResponse)
async def match_single_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> JobMatchResponse:
    """LLM-match one job (staging or career) and persist the result."""
    person_id = f"user_{current_user.id}"
    try:
        return await service.match_single_job(person_id, job_id)
    except MatchBudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{job_id}/promote", response_model=JobPromoteResponse)
async def promote_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> JobPromoteResponse:
    """Promote a scraped JobListing into the career knowledge graph."""
    person_id = f"user_{current_user.id}"
    try:
        return await service.promote_job(job_id=job_id, person_id=person_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
