from __future__ import annotations

import os
import shutil
import tempfile

from fastapi import APIRouter, Body, Depends, File, HTTPException, Response, UploadFile

from ...core.celery_app import celery_app
from ...dependencies import get_current_user
from ...kg.embeddings import KGEmbeddings
from ...kg.ingestion import KGIngestion
from ...kg.repository import KGRepository
from ...models.user import User
from ...schemas.profile import (
    EducationCreate,
    EducationRead,
    EducationUpdate,
    EmploymentCreate,
    EmploymentRead,
    EmploymentUpdate,
    PersonProfileRead,
    PersonProfileUpdate,
    ProfileExtractResponse,
    ProfileSummary,
    TargetRoleCreate,
    TargetRoleRead,
    TargetRoleRefreshResponse,
    TargetRoleUpdate,
)
from ...services.profile_service import ProfileService

router = APIRouter()


def get_profile_service(
    repo: KGRepository = Depends(),
) -> ProfileService:
    embeddings = KGEmbeddings()
    ingestion = KGIngestion(kg_repository=repo, embeddings=embeddings)
    return ProfileService(kg_repository=repo, kg_ingestion=ingestion)


@router.get("/me", response_model=PersonProfileRead)
async def get_profile_details(
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> PersonProfileRead:
    """Contact/header profile (bio, phone, links, location, awards, ...) used
    when rendering the generated CV."""
    return await service.get_profile_details(f"user_{current_user.id}")


@router.patch("/me", response_model=PersonProfileRead)
async def update_profile_details(
    current_user: User = Depends(get_current_user),
    payload: PersonProfileUpdate = Body(...),
    service: ProfileService = Depends(get_profile_service),
) -> PersonProfileRead:
    """Partially update the contact/header profile. Only fields present in
    the request body are changed."""
    return await service.update_profile_details(f"user_{current_user.id}", payload)


@router.get("/summary", response_model=ProfileSummary)
async def get_profile_summary(
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> ProfileSummary:
    return await service.get_summary(f"user_{current_user.id}")


@router.get("/employment", response_model=list[EmploymentRead])
async def list_employment(
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> list[EmploymentRead]:
    return await service.list_employment(f"user_{current_user.id}")


@router.post("/employment", response_model=EmploymentRead)
async def create_employment(
    current_user: User = Depends(get_current_user),
    payload: EmploymentCreate = Body(...),
    service: ProfileService = Depends(get_profile_service),
) -> EmploymentRead:
    return await service.create_employment(f"user_{current_user.id}", payload)


@router.patch("/employment/{employment_id}", response_model=EmploymentRead)
async def update_employment(
    employment_id: str,
    payload: EmploymentUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> EmploymentRead:
    try:
        return await service.update_employment(
            f"user_{current_user.id}", employment_id, payload
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/employment/{employment_id}", status_code=204, response_class=Response)
async def delete_employment(
    employment_id: str,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> Response:
    deleted = await service.delete_employment(f"user_{current_user.id}", employment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Employment not found")
    return Response(status_code=204)


@router.get("/education", response_model=list[EducationRead])
async def list_education(
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> list[EducationRead]:
    return await service.list_education(f"user_{current_user.id}")


@router.post("/education", response_model=EducationRead)
async def create_education(
    current_user: User = Depends(get_current_user),
    payload: EducationCreate = Body(...),
    service: ProfileService = Depends(get_profile_service),
) -> EducationRead:
    return await service.create_education(f"user_{current_user.id}", payload)


@router.patch("/education/{education_id}", response_model=EducationRead)
async def update_education(
    education_id: str,
    payload: EducationUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> EducationRead:
    try:
        return await service.update_education(
            f"user_{current_user.id}", education_id, payload
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/education/{education_id}", status_code=204, response_class=Response)
async def delete_education(
    education_id: str,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> Response:
    deleted = await service.delete_education(f"user_{current_user.id}", education_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Education not found")
    return Response(status_code=204)


@router.post("/upload", response_model=ProfileExtractResponse)
async def upload_profile_document(
    current_user: User = Depends(get_current_user),
    file: UploadFile = File(...),
    service: ProfileService = Depends(get_profile_service),
) -> ProfileExtractResponse:
    """Extract employment/education drafts from an uploaded CV for review.

    Nothing is written to the knowledge graph here - the caller must review
    and submit each confirmed draft via ``POST /employment`` or
    ``POST /education``.
    """
    _ = f"user_{current_user.id}"
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=os.path.splitext(file.filename or "")[1]
    ) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        return await service.extract_profile_drafts(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.get("/target-roles", response_model=list[TargetRoleRead])
async def list_target_roles(
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> list[TargetRoleRead]:
    return await service.list_target_roles(f"user_{current_user.id}")


@router.post("/target-roles", response_model=TargetRoleRead)
async def create_target_role(
    current_user: User = Depends(get_current_user),
    payload: TargetRoleCreate = Body(...),
    service: ProfileService = Depends(get_profile_service),
) -> TargetRoleRead:
    """Create a TargetRole and immediately queue a market-sample scrape for
    it (title + location) - required_skills is derived from that sample,
    never typed by hand."""
    role = await service.create_target_role(f"user_{current_user.id}", payload)
    celery_app.send_task(
        "app.tasks.role_tasks.refresh_target_role_sample",
        kwargs={"role_id": role.id},
    )
    return role


@router.post("/target-roles/{role_id}/refresh", response_model=TargetRoleRefreshResponse)
async def refresh_target_role(
    role_id: str,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> TargetRoleRefreshResponse:
    """Re-queue the market-sample scrape for an existing TargetRole."""
    role = await service.get_target_role(f"user_{current_user.id}", role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Target role not found")
    await service.mark_target_role_sample_status(role_id, "scraping")
    task = celery_app.send_task(
        "app.tasks.role_tasks.refresh_target_role_sample",
        kwargs={"role_id": role_id},
    )
    return TargetRoleRefreshResponse(id=role_id, sample_status="scraping", task_id=task.id)


@router.patch("/target-roles/{role_id}", response_model=TargetRoleRead)
async def update_target_role(
    role_id: str,
    payload: TargetRoleUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> TargetRoleRead:
    try:
        return await service.update_target_role(
            f"user_{current_user.id}", role_id, payload
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/target-roles/{role_id}", status_code=204, response_class=Response)
async def delete_target_role(
    role_id: str,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> Response:
    deleted = await service.delete_target_role(f"user_{current_user.id}", role_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Target role not found")
    return Response(status_code=204)
