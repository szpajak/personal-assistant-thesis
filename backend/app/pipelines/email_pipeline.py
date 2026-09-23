"""Pipeline for processing and classifying emails."""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import END, StateGraph

from ..config import settings
from ..kg.chains import get_chat_llm
from ..kg.embeddings import KGEmbeddings
from ..kg.ingestion import KGIngestion
from ..kg.repository import KGRepository
from ..prompts.email_prompts import EMAIL_CLASSIFICATION_PROMPT
from ..utils.email_heuristics import (
    apply_keyword_stage,
    choose_application,
    heuristic_email_analysis,
    repair_email_link,
    truncate_email_body,
)

logger = logging.getLogger(__name__)

# Maps the LLM-classified application_stage onto the exact status vocabulary
# used by the Applications Kanban board (frontend/src/components/applications
# /ApplicationDetailSheet.tsx: Applied/Responded/Interview/Offer/Rejected).
_APPLICATION_STAGE_TO_STATUS = {
    "applied_ack": "Responded",
    "interview_invite": "Interview",
    "assessment": "Interview",
    "offer": "Offer",
    "rejection": "Rejected",
}


class EmailPipelineState(TypedDict):
    """State for the email processing pipeline."""

    person_id: str
    raw_emails: list[dict[str, Any]]
    processed_emails: list[dict[str, Any]]


class EmailPipeline:
    """Handles email processing and KG ingestion using LangGraph."""

    def __init__(
        self,
        kg_repository: KGRepository,
        kg_ingestion: KGIngestion | None = None,
    ) -> None:
        self.kg_repository = kg_repository
        self.kg_ingestion = kg_ingestion or KGIngestion(
            kg_repository=kg_repository,
            embeddings=KGEmbeddings(kg_repository=kg_repository),
            scrape_ttl_days=settings.job_scrape_ttl_days,
        )
        # Short JSON classification (classification, summary, action flag).
        self.llm = get_chat_llm(temperature=0, max_tokens=400)
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        """Build the LangGraph StateGraph."""
        workflow = StateGraph(EmailPipelineState)

        workflow.add_node("classify_emails", self.classify_emails)
        workflow.add_node("ingest_into_kg", self.ingest_into_kg)

        workflow.set_entry_point("classify_emails")
        workflow.add_edge("classify_emails", "ingest_into_kg")
        workflow.add_edge("ingest_into_kg", END)

        return workflow.compile()

    async def classify_emails(self, state: EmailPipelineState) -> dict[str, Any]:
        """Classify each raw email using heuristics first, then LLM."""
        processed = []
        chain = EMAIL_CLASSIFICATION_PROMPT | self.llm | JsonOutputParser()

        for email in state["raw_emails"]:
            subject = str(email.get("subject", "") or "")
            body = str(email.get("body", "") or "")
            sender = str(email.get("sender", "") or "")

            heuristic = heuristic_email_analysis(subject, body, sender)
            if heuristic is not None:
                analysis = heuristic
            else:
                body_for_llm = truncate_email_body(body)
                try:
                    analysis = await chain.ainvoke(
                        {"subject": subject, "body": body_for_llm}
                    )
                except Exception as e:
                    # One malformed LLM reply must not abort the whole poll batch.
                    logger.error(
                        "Email classification failed for id=%s: %s",
                        email.get("id"),
                        e,
                    )
                    analysis = {
                        "classification": "other",
                        "summary": subject[:100] or "Classification failed.",
                        "action_required": False,
                        "entity_name": "",
                        "application_stage": "none",
                    }
            if not isinstance(analysis, dict):
                analysis = {
                    "classification": "other",
                    "summary": subject[:100] or "Classification failed.",
                    "action_required": False,
                    "entity_name": "",
                    "application_stage": "none",
                }
            # Keyword stage fills in when the model left the stage empty.
            # An explicit model stage is left unchanged.
            analysis = apply_keyword_stage(analysis, subject, body)
            stage = str(analysis.get("application_stage") or "none")
            if stage in _APPLICATION_STAGE_TO_STATUS:
                matched = await self._match_application(
                    person_id=state["person_id"],
                    entity_name=str(analysis.get("entity_name") or ""),
                    subject=subject,
                    body=body,
                    sender=sender,
                )
                if matched:
                    # Link this message to that application only. Do not
                    # rewrite the company onto a different offer.
                    analysis["application_id"] = str(
                        matched.get("application_id") or ""
                    )
                    company = str(matched.get("company") or "").strip()
                    if company:
                        analysis["entity_name"] = company
                else:
                    # A status email that does not name one application must
                    # not fall through to a company-only link on another job.
                    analysis["entity_name"] = ""
                    analysis["application_id"] = ""
            processed.append({**email, "analysis": analysis})

        return {"processed_emails": processed}

    async def ingest_into_kg(self, state: EmailPipelineState) -> dict[str, Any]:
        """Ingest processed emails into the KG, linking ownership + applications."""
        person_id = state["person_id"]

        for email in state["processed_emails"]:
            analysis = email.get("analysis") or {}
            entity_name = analysis.get("entity_name")
            message_id = str(email.get("message_id") or "").strip() or None

            application_id = str(analysis.get("application_id") or "").strip() or None
            ingest_kwargs: dict[str, Any] = {
                "subject": str(email.get("subject", "")),
                "sender": str(email.get("sender", "")),
                "classification": str(analysis.get("classification", "other")),
                "summary": str(analysis.get("summary", "")),
                "metadata": {"received_at": email.get("received_at")},
                "person_id": person_id,
                "entity_name": entity_name,
                "message_id": message_id,
            }
            if application_id:
                ingest_kwargs["application_id"] = application_id
            email_id = await self.kg_ingestion.ingest_email(**ingest_kwargs)
            email["kg_id"] = email_id

            # Skip application updates when ingest could not produce an id.
            if email_id:
                await self._apply_application_stage_update(
                    person_id=person_id,
                    entity_name=entity_name,
                    application_stage=str(analysis.get("application_stage", "none")),
                    application_id=application_id,
                )

        return {}

    async def _list_applications(self, person_id: str) -> list[dict[str, Any]]:
        """Applications owned by ``person_id``, newest first."""
        try:
            rows = await self.kg_repository.query(
                """
                MATCH (p:Person {id: $person_id})-[:APPLIED_TO]->(a:Application)
                      -[:FOR_OFFER]->(j:JobOffer)
                OPTIONAL MATCH (j)-[:POSTED_BY]->(c:Company)
                RETURN a.id AS application_id,
                       coalesce(c.name, j.company, '') AS company,
                       coalesce(j.title, '') AS title
                ORDER BY a.applied_at DESC
                """,
                {"person_id": person_id},
            )
        except Exception as exc:
            logger.warning("Application lookup for email linking failed: %s", exc)
            return []
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

    async def _match_application(
        self,
        *,
        person_id: str,
        entity_name: str,
        subject: str,
        body: str,
        sender: str,
    ) -> dict[str, Any] | None:
        """Return the one application this status email belongs to."""
        rows = await self._list_applications(person_id)
        if not rows:
            return None
        return choose_application(
            rows,
            entity_name=entity_name,
            subject=subject,
            body=body,
            sender=sender,
        )

    async def reconcile_application_emails(self, person_id: str) -> None:
        """Detach or move emails that were linked to the wrong application.

        Uses the stored subject and summary (the body is not kept on the
        Email node). A link that still names its own job is left alone.
        """
        try:
            rows = await self.kg_repository.query(
                """
                MATCH (p:Person {id: $person_id})-[:APPLIED_TO]->(a:Application)
                      -[:FOR_OFFER]->(j:JobOffer)
                OPTIONAL MATCH (j)-[:POSTED_BY]->(c:Company)
                OPTIONAL MATCH (a)-[:HAS_EMAIL]->(e:Email)
                RETURN a.id AS application_id,
                       coalesce(c.name, j.company, '') AS company,
                       coalesce(j.title, '') AS title,
                       e.id AS email_id,
                       e.subject AS subject,
                       e.sender AS sender,
                       e.summary AS summary
                ORDER BY a.applied_at DESC
                """,
                {"person_id": person_id},
            )
        except Exception as exc:
            logger.warning("Could not list application emails to repair: %s", exc)
            return
        if not isinstance(rows, list):
            return

        applications: dict[str, dict[str, Any]] = {}
        links: list[dict[str, str]] = []
        seen_links: set[tuple[str, str]] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            application_id = str(row.get("application_id") or "")
            if not application_id:
                continue
            applications.setdefault(
                application_id,
                {
                    "application_id": application_id,
                    "company": str(row.get("company") or ""),
                    "title": str(row.get("title") or ""),
                },
            )
            email_id = str(row.get("email_id") or "")
            if not email_id or (application_id, email_id) in seen_links:
                continue
            seen_links.add((application_id, email_id))
            links.append(
                {
                    "application_id": application_id,
                    "email_id": email_id,
                    "subject": str(row.get("subject") or ""),
                    "sender": str(row.get("sender") or ""),
                    "summary": str(row.get("summary") or ""),
                }
            )

        catalog = list(applications.values())
        for link in links:
            decision = repair_email_link(
                catalog,
                linked_application_id=link["application_id"],
                subject=link["subject"],
                body=link["summary"],
                sender=link["sender"],
            )
            if decision is None or decision == link["application_id"]:
                continue
            await self._unlink_email(link["application_id"], link["email_id"])
            if not decision:
                logger.info(
                    "Detached email %s from application %s",
                    link["email_id"],
                    link["application_id"],
                )
                continue
            await self.kg_repository.upsert_relationship(
                from_label="Application",
                from_id=decision,
                relationship_type="HAS_EMAIL",
                to_label="Email",
                to_id=link["email_id"],
            )
            logger.info(
                "Moved email %s from application %s to %s",
                link["email_id"],
                link["application_id"],
                decision,
            )

    async def _unlink_email(self, application_id: str, email_id: str) -> None:
        await self.kg_repository.query(
            """
            MATCH (a:Application {id: $application_id})
                  -[rel:HAS_EMAIL]->(e:Email {id: $email_id})
            DELETE rel
            """,
            {"application_id": application_id, "email_id": email_id},
        )

    async def _apply_application_stage_update(
        self,
        person_id: str,
        entity_name: str | None,
        application_stage: str,
        application_id: str | None = None,
    ) -> None:
        """Advance a matching Application's status per the classified email.

        Best-effort: matches the application by the same company-name
        heuristic used to link the email itself, then only writes when the
        stage maps onto a known Kanban status (silently no-ops otherwise so
        cold outreach / unrelated career emails never mutate an application).
        """
        new_status = _APPLICATION_STAGE_TO_STATUS.get(application_stage)
        if not new_status:
            return
        if application_id:
            await self.kg_repository.upsert_node(
                "Application", {"id": application_id, "status": new_status}
            )
            return
        if not entity_name:
            return

        from ..utils.skill_ids import company_id

        comp_id = company_id(entity_name)
        results = await self.kg_repository.query(
            """
            MATCH (p:Person {id: $person_id})-[:APPLIED_TO]->(a:Application)
                  -[:FOR_OFFER]->(j:JobOffer)-[:POSTED_BY]->(c:Company {id: $comp_id})
            RETURN a.id AS application_id
            ORDER BY a.applied_at DESC
            LIMIT 1
            """,
            {"person_id": person_id, "comp_id": comp_id},
        )
        if not isinstance(results, list) or not results:
            return
        row = results[0] if isinstance(results[0], dict) else None
        application_id = row.get("application_id") if row else None
        if not application_id:
            return

        application_id = str(application_id)
        await self.kg_repository.upsert_node(
            "Application", {"id": application_id, "status": new_status}
        )

    async def run(
        self,
        raw_emails: list[dict[str, Any]],
        person_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run the pipeline.

        ``person_id`` defaults to the configured primary person since email
        polling runs as a background job with no authenticated request
        context (single IMAP mailbox for the whole app today).
        """
        initial_state: EmailPipelineState = {
            "person_id": person_id or settings.primary_person_id,
            "raw_emails": raw_emails,
            "processed_emails": [],
        }

        final_state: EmailPipelineState = await self.graph.ainvoke(initial_state)
        return list(final_state["processed_emails"])
