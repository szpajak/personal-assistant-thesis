from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ...dependencies import get_current_user
from ...kg.embeddings import KGEmbeddings
from ...kg.ingestion import KGIngestion
from ...kg.repository import KGRepository
from ...models.user import User
from ...pipelines.email_pipeline import EmailPipeline
from ...services.email_service import EmailService

router = APIRouter()


def get_email_service(
    repo: KGRepository = Depends(),
) -> EmailService:
    ingestion = KGIngestion(kg_repository=repo, embeddings=KGEmbeddings())
    pipeline = EmailPipeline(kg_repository=repo)
    return EmailService(kg_ingestion=ingestion, email_pipeline=pipeline)


@router.post("/sync", response_model=list[dict[str, Any]])
async def sync_emails(
    current_user: User = Depends(get_current_user),
    service: EmailService = Depends(get_email_service),
) -> list[dict[str, Any]]:
    """Poll inbox for new emails and process them."""
    person_id = f"user_{current_user.id}"
    processed_emails = await service.poll_inbox(person_id=person_id)
    return processed_emails
