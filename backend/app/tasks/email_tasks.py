"""Celery background tasks for email processing."""

from __future__ import annotations

import asyncio
import logging
import ssl

from sqlalchemy import select

from ..config import settings
from ..core.celery_app import celery_app
from ..core.database import celery_db_session
from ..kg.embeddings import KGEmbeddings
from ..kg.ingestion import KGIngestion
from ..kg.repository import KGRepository
from ..models.user import User
from ..pipelines.email_pipeline import EmailPipeline
from ..services.email_service import EmailService

logger = logging.getLogger(__name__)


async def resolve_primary_person_id() -> str:
    """Map the seeded/default Postgres user to the app Person id ``user_{id}``.

    Falls back to ``settings.primary_person_id`` when no users exist yet.
    """
    try:
        async with celery_db_session() as session:
            result = await session.execute(
                select(User).where(User.email == "test@example.com").limit(1)
            )
            user = result.scalar_one_or_none()
            if user is None:
                result = await session.execute(select(User).order_by(User.id).limit(1))
                user = result.scalar_one_or_none()
            if user is not None:
                return f"user_{user.id}"
    except Exception as exc:
        logger.warning("Could not resolve primary person from Postgres: %s", exc)
    return settings.primary_person_id


@celery_app.task  # type: ignore[untyped-decorator]
def poll_email_inbox() -> None:
    """Poll IMAP inbox for new emails and classify them."""

    async def _run() -> None:
        person_id = await resolve_primary_person_id()
        repo = KGRepository()
        embeddings = KGEmbeddings(kg_repository=repo)
        ingestion = KGIngestion(kg_repository=repo, embeddings=embeddings)
        pipeline = EmailPipeline(kg_repository=repo)
        service = EmailService(kg_ingestion=ingestion, email_pipeline=pipeline)

        await service.poll_inbox(person_id=person_id)

    try:
        asyncio.run(_run())
        logger.info("Email polling task completed")
    except ssl.SSLCertVerificationError as exc:
        logger.error(
            "Email polling skipped: TLS certificate verification failed (%s). "
            "For self-signed mail servers set IMAP_VERIFY_SSL=false or provide "
            "IMAP_CA_FILE in .env.",
            exc,
        )
    except Exception as e:
        logger.error(f"Email polling task failed: {e}")
        raise
