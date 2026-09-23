from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...db.generation_cache_repository import GenerationCacheRepository
from ...db.job_listing_repository import JobListingRepository
from ...dependencies import get_current_user, get_db_session
from ...kg.embeddings import KGEmbeddings
from ...kg.graphrag import GraphRAG
from ...kg.ingestion import KGIngestion
from ...kg.repository import KGRepository
from ...models.user import User
from ...pipelines.cv_pipeline import CVPipeline
from ...services.cv_service import CVService

router = APIRouter()


def get_cv_service(
    repo: KGRepository = Depends(),
    db: AsyncSession = Depends(get_db_session),
) -> CVService:
    embeddings = KGEmbeddings(kg_repository=repo)
    graph_rag = GraphRAG(kg_repository=repo, embeddings=embeddings)
    pipeline = CVPipeline(kg_repository=repo, graph_rag=graph_rag)
    ingestion = KGIngestion(
        kg_repository=repo,
        embeddings=embeddings,
        scrape_ttl_days=settings.job_scrape_ttl_days,
    )
    return CVService(
        kg_repository=repo,
        graphrag=graph_rag,
        cv_pipeline=pipeline,
        job_listing_repository=JobListingRepository(db=db),
        generation_cache_repository=GenerationCacheRepository(db=db),
        kg_ingestion=ingestion,
    )


@router.post("/generate")
async def generate_cv(
    current_user: User = Depends(get_current_user),
    job_id: str = Query(..., description="Job Offer ID to tailor the CV for"),
    force: bool = Query(False, description="Bypass cache and regenerate"),
    service: CVService = Depends(get_cv_service),
) -> dict[str, object]:
    """Generate a personalized CV for a specific job offer."""
    person_id = f"user_{current_user.id}"
    result = await service.generate_personalized_cv(
        job_id=job_id,
        person_id=person_id,
        force=force,
        display_name=current_user.full_name,
    )
    return {
        "cv_content": result["cv_content"],
        "cached": result["cached"],
    }


@router.get("/download")
async def download_cv(
    current_user: User = Depends(get_current_user),
    job_id: str = Query(..., description="Job Offer ID"),
    force: bool = Query(False, description="Bypass cache and regenerate"),
    service: CVService = Depends(get_cv_service),
) -> FileResponse:
    """Download a personalized CV as a PDF."""
    person_id = f"user_{current_user.id}"
    try:
        result = await service.generate_personalized_cv(
            job_id=job_id,
            person_id=person_id,
            force=force,
            display_name=current_user.full_name,
        )
        file_path = await service.export_cv_to_pdf(
            cv_content=str(result["cv_content"]), filename=f"CV_{job_id}.pdf"
        )
        return FileResponse(
            path=file_path, filename="Personalized_CV.pdf", media_type="application/pdf"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
