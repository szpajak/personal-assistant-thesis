from __future__ import annotations

import os
import shutil
import tempfile

from fastapi import APIRouter, Body, Depends, File, UploadFile

from ...dependencies import get_current_user
from ...kg.embeddings import KGEmbeddings
from ...kg.ingestion import KGIngestion
from ...kg.repository import KGRepository
from ...models.user import User
from ...schemas.certificates import (
    CertificateCreate,
    CertificateExtractResponse,
    CertificateRead,
)
from ...services.certificate_service import CertificateService

router = APIRouter()


def get_certificate_service(
    repo: KGRepository = Depends(),
) -> CertificateService:
    embeddings = KGEmbeddings()
    ingestion = KGIngestion(kg_repository=repo, embeddings=embeddings)
    return CertificateService(kg_repository=repo, kg_ingestion=ingestion)


@router.get("/", response_model=list[CertificateRead])
async def list_certificates(
    current_user: User = Depends(get_current_user),
    service: CertificateService = Depends(get_certificate_service),
) -> list[CertificateRead]:
    person_id = f"user_{current_user.id}"
    return await service.list_certificates(person_id)


@router.post("/", response_model=CertificateRead)
async def create_certificate(
    current_user: User = Depends(get_current_user),
    payload: CertificateCreate = Body(...),
    service: CertificateService = Depends(get_certificate_service),
) -> CertificateRead:
    person_id = f"user_{current_user.id}"
    return await service.create_certificate(person_id, payload)


@router.post("/upload", response_model=CertificateExtractResponse)
async def upload_certificate_document(
    current_user: User = Depends(get_current_user),
    file: UploadFile = File(...),
    service: CertificateService = Depends(get_certificate_service),
) -> CertificateExtractResponse:
    """Extract a certificate draft from an uploaded document for user review.

    Nothing is written to the knowledge graph here - the caller must review
    and submit the confirmed draft via ``POST /`` to actually create it.
    """
    _ = f"user_{current_user.id}"
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=os.path.splitext(file.filename or "")[1]
    ) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        drafts = await service.extract_certificate_drafts(tmp_path)
        return CertificateExtractResponse(drafts=drafts)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
