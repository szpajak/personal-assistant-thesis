from __future__ import annotations

import os
import shutil
import tempfile
from typing import Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, Response, UploadFile

from ...dependencies import get_current_user
from ...kg.embeddings import KGEmbeddings
from ...kg.ingestion import KGIngestion
from ...kg.repository import KGRepository
from ...models.user import User
from ...schemas.portfolio import (
    ProjectCreate,
    ProjectExtractResponse,
    ProjectRead,
    ProjectUpdate,
    PublicPortfolioExport,
)
from ...services.portfolio_service import PortfolioService

router = APIRouter()


def get_portfolio_service(
    repo: KGRepository = Depends(),
) -> PortfolioService:
    embeddings = KGEmbeddings()
    ingestion = KGIngestion(kg_repository=repo, embeddings=embeddings)
    return PortfolioService(kg_repository=repo, kg_ingestion=ingestion)


@router.get("/", response_model=list[ProjectRead])
async def list_portfolio(
    status: str | None = Query(
        default=None, description="Filter by planned | in_progress | finished"
    ),
    current_user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
) -> list[ProjectRead]:
    person_id = f"user_{current_user.id}"
    resolved = status if status in {"planned", "in_progress", "finished"} else None
    return await service.list_projects(person_id, status=resolved)


@router.post("/", response_model=ProjectRead)
async def create_project(
    current_user: User = Depends(get_current_user),
    project: ProjectCreate = Body(...),
    service: PortfolioService = Depends(get_portfolio_service),
) -> ProjectRead:
    person_id = f"user_{current_user.id}"
    return await service.create_project(person_id, project)


@router.get("/export/{person_id}", response_model=PublicPortfolioExport)
async def export_public_portfolio(
    person_id: str,
    service: PortfolioService = Depends(get_portfolio_service),
) -> PublicPortfolioExport:
    """Public, unauthenticated read-only export used by the static portfolio
    site generator (backend/scripts/generate_portfolio_site.py) and any other
    consumer that wants to render a public profile. Includes contact links,
    employment, and education alongside projects/skills/certificates.
    Deliberately excludes private data (applications, emails, learning
    plans, target roles) and planned (not-yet-started) projects.
    """
    return await service.export_public_portfolio(person_id)


@router.post("/from-plan", response_model=ProjectRead)
async def create_project_from_plan(
    current_user: User = Depends(get_current_user),
    item: dict[str, Any] = Body(...),
    service: PortfolioService = Depends(get_portfolio_service),
) -> ProjectRead:
    """Create a planned project from a learning plan item."""
    person_id = f"user_{current_user.id}"
    return await service.create_project_from_plan(person_id, item)


@router.post("/from-suggestion", response_model=ProjectRead)
async def create_project_from_suggestion(
    current_user: User = Depends(get_current_user),
    suggestion: dict[str, Any] = Body(...),
    service: PortfolioService = Depends(get_portfolio_service),
) -> ProjectRead:
    """Create a planned multi-skill project from a skill-analysis suggestion."""
    person_id = f"user_{current_user.id}"
    return await service.create_project_from_suggestion(person_id, suggestion)


@router.post("/upload", response_model=ProjectExtractResponse)
async def upload_project_document(
    current_user: User = Depends(get_current_user),
    file: UploadFile = File(...),
    service: PortfolioService = Depends(get_portfolio_service),
) -> ProjectExtractResponse:
    """Extract project draft(s) from an uploaded document for user review.

    Nothing is written to the knowledge graph here - the caller must review
    the returned draft(s) and submit each confirmed one via ``POST /`` (with
    ``skip_enrichment=True``) to actually create the project.
    """
    _ = f"user_{current_user.id}"
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=os.path.splitext(file.filename or "")[1]
    ) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        drafts = await service.extract_project_drafts(tmp_path)
        return ProjectExtractResponse(drafts=drafts)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: str,
    payload: ProjectUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
) -> ProjectRead:
    person_id = f"user_{current_user.id}"
    try:
        return await service.update_project(person_id, project_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{project_id}", status_code=204, response_class=Response)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
) -> Response:
    person_id = f"user_{current_user.id}"
    deleted = await service.delete_project(person_id, project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return Response(status_code=204)
