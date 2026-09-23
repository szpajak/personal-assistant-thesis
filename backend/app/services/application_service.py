"""Service for managing job applications."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from ..config import settings
from ..db.job_listing_repository import JobListingRepository, listing_to_dict
from ..kg.embeddings import KGEmbeddings
from ..kg.ingestion import KGIngestion
from ..kg.repository import KGRepository
from ..schemas.applications import ApplicationCreate, ApplicationRead, ApplicationUpdate
from ..schemas.email import EmailRead
from ..schemas.jobs import JobOfferRead
from ..utils.neo4j_types import neo4j_to_python
from ..utils.skill_ids import canonicalize_skill_list

logger = logging.getLogger(__name__)

# Kanban columns in frontend/src/components/applications/KanbanBoard.tsx.
# Incoming aliases (Jobs "Apply" used to send lowercase "applied") are mapped
# onto this vocabulary so cards are not dropped on the floor.
_KANBAN_STATUS_ALIASES = {
    "applied": "Applied",
    "responded": "Responded",
    "interview": "Interview",
    "interviewing": "Interview",
    "offer": "Offer",
    "rejected": "Rejected",
}


def canonicalize_application_status(status: str | None) -> str:
    """Map free-form status strings onto the Kanban column ids."""
    raw = (status or "").strip()
    if not raw:
        return "Applied"
    return _KANBAN_STATUS_ALIASES.get(raw.lower(), raw)


class ApplicationService:
    """Manage job applications."""

    def __init__(
        self,
        kg_repository: KGRepository,
        job_listing_repository: JobListingRepository,
        kg_ingestion: KGIngestion | None = None,
    ) -> None:
        self.kg_repository = kg_repository
        self.job_listing_repository = job_listing_repository
        self.kg_ingestion = kg_ingestion or KGIngestion(
            kg_repository=kg_repository,
            embeddings=KGEmbeddings(kg_repository=kg_repository),
            scrape_ttl_days=settings.job_scrape_ttl_days,
        )

    async def create_application(
        self,
        person_id: str,
        payload: ApplicationCreate,
    ) -> ApplicationRead:
        """Create a new job application, promoting the scraped listing first if needed."""
        try:
            listing_row = await self.job_listing_repository.get_by_id(
                payload.job_offer_id
            )
            listing = listing_to_dict(listing_row) if listing_row else {}

            job_props, _ = await self.kg_ingestion.promote_job(
                job_id=payload.job_offer_id,
                listing=listing,
                person_id=person_id,
                extract_skills=True,
            )
            if listing_row:
                await self.job_listing_repository.delete_by_id(payload.job_offer_id)

            app_id = str(uuid.uuid4())
            status = canonicalize_application_status(payload.status)
            app_properties = {
                "id": app_id,
                "status": status,
                "applied_at": payload.applied_at,
                "notes": payload.notes,
            }

            await self.kg_repository.upsert_node("Application", app_properties)
            await self.kg_repository.upsert_relationship(
                from_label="Person",
                from_id=person_id,
                relationship_type="APPLIED_TO",
                to_label="Application",
                to_id=app_id,
            )
            await self.kg_repository.upsert_relationship(
                from_label="Application",
                from_id=app_id,
                relationship_type="FOR_OFFER",
                to_label="JobOffer",
                to_id=payload.job_offer_id,
            )

            job_offer = self._to_job_read(job_props)
            logger.info(f"Created application {app_id} for person {person_id}")

            return ApplicationRead(
                id=app_id,
                job_offer=job_offer,
                job_offer_id=payload.job_offer_id,
                status=status,
                applied_at=payload.applied_at,
                notes=payload.notes,
            )

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to create application: {e}")
            raise

    async def list_applications(
        self,
        person_id: str,
    ) -> list[ApplicationRead]:
        """List all applications for a person."""
        query = """
        MATCH (p:Person {id: $person_id})-[:APPLIED_TO]->(a:Application)
        OPTIONAL MATCH (a)-[:FOR_OFFER]->(j:JobOffer)
        RETURN properties(a) as app, properties(j) as job
        """
        results = await self.kg_repository.query(query, {"person_id": person_id})

        applications: list[ApplicationRead] = []
        for r in results:
            try:
                applications.append(
                    self._to_application_read(r.get("app") or {}, r.get("job"))
                )
            except Exception as e:
                logger.warning(
                    "Skipping malformed application row id=%s: %s",
                    (r.get("app") or {}).get("id"),
                    e,
                )
        return applications

    async def list_application_emails(
        self,
        person_id: str,
        application_id: str,
    ) -> list[EmailRead] | None:
        """List emails linked to an application owned by the given person.

        Returns ``None`` when the application does not exist or is not owned
        by ``person_id``; otherwise returns the (possibly empty) email list.
        """
        try:
            ownership = await self.kg_repository.query(
                """
                MATCH (p:Person {id: $person_id})-[:APPLIED_TO]->(a:Application {id: $application_id})
                RETURN a.id AS id
                LIMIT 1
                """,
                {"person_id": person_id, "application_id": application_id},
            )
            if not ownership:
                return None

            results = await self.kg_repository.query(
                """
                MATCH (a:Application {id: $application_id})-[:HAS_EMAIL]->(e:Email)
                RETURN properties(e) AS email
                ORDER BY coalesce(e.received_at, '') DESC
                """,
                {"application_id": application_id},
            )
            emails: list[EmailRead] = []
            for row in results:
                email = neo4j_to_python(row.get("email") or {})
                received_at = email.get("received_at")
                emails.append(
                    EmailRead(
                        id=str(email.get("id", "")),
                        subject=str(email.get("subject") or ""),
                        sender=str(email.get("sender") or ""),
                        received_at=None if received_at is None else str(received_at),
                        summary=email.get("summary"),
                        classification=email.get("classification"),
                    )
                )
            return emails
        except Exception as e:
            logger.error(f"Failed to list emails for application {application_id}: {e}")
            raise

    async def update_application(
        self,
        application_id: str,
        payload: ApplicationUpdate,
    ) -> ApplicationRead | None:
        """Update an application."""
        try:
            existing = await self.kg_repository.get_node("Application", application_id)
            if not existing:
                return None

            patch = {k: v for k, v in payload.model_dump().items() if v is not None}
            if "status" in patch:
                patch["status"] = canonicalize_application_status(patch["status"])
            updated = {**existing, **patch}
            await self.kg_repository.upsert_node("Application", updated)

            query = """
            MATCH (a:Application {id: $id})
            OPTIONAL MATCH (a)-[:FOR_OFFER]->(j:JobOffer)
            RETURN properties(a) as app, properties(j) as job
            """
            results = await self.kg_repository.query(query, {"id": application_id})
            if not results:
                return None
            return self._to_application_read(
                results[0].get("app") or {}, results[0].get("job")
            )
        except Exception as e:
            logger.error(f"Failed to update application: {e}")
            raise

    def _to_application_read(
        self, app: dict[str, Any], job: dict[str, Any] | None
    ) -> ApplicationRead:
        app = neo4j_to_python(app) or {}
        job = neo4j_to_python(job) if job else None
        return ApplicationRead(
            id=str(app.get("id", "")),
            job_offer_id=(job or {}).get("id") or "",
            status=canonicalize_application_status(str(app.get("status") or "")),
            applied_at=app.get("applied_at"),
            notes=app.get("notes"),
            job_offer=self._to_job_read(job) if job else None,
        )

    def _to_job_read(self, data: dict) -> JobOfferRead:
        data = neo4j_to_python(data) or {}
        scraped_at = data.get("scraped_at")
        if isinstance(scraped_at, str):
            try:
                scraped_at = datetime.fromisoformat(scraped_at)
            except ValueError:
                scraped_at = datetime.now()
        elif not isinstance(scraped_at, datetime):
            scraped_at = datetime.now()

        skills = data.get("required_skills") or []
        if not isinstance(skills, list):
            skills = []

        return JobOfferRead(
            id=str(data.get("id", "")),
            title=str(data.get("title", "")),
            company=str(data.get("company", "")),
            url=str(data.get("url", "")),
            description=str(data.get("description", "")),
            required_skills=canonicalize_skill_list([str(s) for s in skills]),
            scraped_at=scraped_at,
            tier="career",
        )
