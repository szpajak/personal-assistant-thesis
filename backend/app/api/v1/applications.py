from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...db.job_listing_repository import JobListingRepository
from ...dependencies import get_current_user, get_db_session
from ...kg.embeddings import KGEmbeddings
from ...kg.ingestion import KGIngestion
from ...kg.repository import KGRepository
from ...models.user import User
from ...schemas.applications import (
    ApplicationCreate,
    ApplicationRead,
    ApplicationUpdate,
)
from ...schemas.email import EmailRead
from ...services.application_service import ApplicationService

router = APIRouter()


def get_application_service(
    repo: KGRepository = Depends(),
    db: AsyncSession = Depends(get_db_session),
) -> ApplicationService:
    embeddings = KGEmbeddings(kg_repository=repo)
    ingestion = KGIngestion(
        kg_repository=repo,
        embeddings=embeddings,
        scrape_ttl_days=settings.job_scrape_ttl_days,
    )
    return ApplicationService(
        kg_repository=repo,
        job_listing_repository=JobListingRepository(db=db),
        kg_ingestion=ingestion,
    )


@router.get("/", response_model=list[ApplicationRead])
async def list_applications(
    current_user: User = Depends(get_current_user),
    service: ApplicationService = Depends(get_application_service),
) -> list[ApplicationRead]:
    # KG ID for the person is derived from the authenticated user
    person_id = f"user_{current_user.id}"
    applications: list[ApplicationRead] = await service.list_applications(person_id)
    return applications


@router.post("/", response_model=ApplicationRead)
async def create_application(
    current_user: User = Depends(get_current_user),
    payload: ApplicationCreate = Body(...),
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationRead:
    person_id = f"user_{current_user.id}"
    try:
        return await service.create_application(person_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{id}/emails", response_model=list[EmailRead])
async def list_application_emails(
    id: str,
    current_user: User = Depends(get_current_user),
    service: ApplicationService = Depends(get_application_service),
) -> list[EmailRead]:
    """Return emails linked to an application owned by the current user."""
    person_id = f"user_{current_user.id}"
    emails = await service.list_application_emails(person_id, id)
    if emails is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return emails


@router.patch("/{id}", response_model=ApplicationRead)
async def update_application(
    id: str,
    payload: ApplicationUpdate = Body(...),
    service: ApplicationService = Depends(get_application_service),
    current_user: User = Depends(get_current_user),  # Added for protection
) -> ApplicationRead:
    application = await service.update_application(id, payload)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application
