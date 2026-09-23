"""Service for managing certificates in the KG."""

from __future__ import annotations

import logging

from ..kg.chains import create_skill_extraction_chain
from ..kg.ingestion import KGIngestion
from ..kg.repository import KGRepository
from ..schemas.certificates import CertificateCreate, CertificateDraft, CertificateRead
from ..utils.llm_json import extract_json_array_from_llm_output
from ..utils.parsing import DocumentParser, truncate_document_text

logger = logging.getLogger(__name__)


class CertificateService:
    """Manage certificates: CRUD + document-upload extraction."""

    def __init__(
        self,
        kg_repository: KGRepository,
        kg_ingestion: KGIngestion,
    ) -> None:
        self.kg_repository = kg_repository
        self.kg_ingestion = kg_ingestion

    async def create_certificate(
        self,
        person_id: str,
        payload: CertificateCreate,
    ) -> CertificateRead:
        """Create a certificate and validate the skills it demonstrates."""
        cert_id = await self.kg_ingestion.ingest_certificate(
            title=payload.title,
            issuer=payload.issuer,
            issued_at=payload.issued_at,
            document_url=payload.document_url,
            person_id=person_id,
            validated_skills=payload.validated_skills,
        )
        return CertificateRead(id=cert_id, **payload.model_dump())

    async def list_certificates(self, person_id: str) -> list[CertificateRead]:
        """List all certificates for a person."""
        try:
            certs = await self.kg_repository.find_related_nodes(
                start_label="Person",
                start_id=person_id,
                relationship_type="HAS_CERTIFICATE",
                hops=1,
            )
            results: list[CertificateRead] = []
            for c in certs:
                skills = await self.kg_repository.find_related_nodes(
                    start_label="Certificate",
                    start_id=c.get("id", ""),
                    relationship_type="VALIDATES",
                    hops=1,
                )
                results.append(
                    CertificateRead(
                        id=c.get("id", ""),
                        title=c.get("title", ""),
                        issuer=c.get("issuer", ""),
                        issued_at=c.get("issued_at"),
                        document_url=c.get("document_url", ""),
                        validated_skills=[
                            s.get("name", "") for s in skills if s.get("name")
                        ],
                    )
                )
            return results
        except Exception as e:
            logger.error(f"Failed to list certificates: {e}")
            return []

    async def extract_certificate_drafts(
        self, file_path: str
    ) -> list[CertificateDraft]:
        """Parse a certificate document (PDF/image-to-text) and extract a
        draft for user review. Nothing is written to the KG here.
        """
        parser = DocumentParser()
        parsed_doc = await parser.parse_file(file_path)
        text = parsed_doc["text"]

        skills: list[str] = []
        try:
            chain = create_skill_extraction_chain()
            response = await chain.ainvoke({"text": truncate_document_text(text)})
            skills_data = extract_json_array_from_llm_output(str(response.content))
            skills = [
                str(s.get("name", "")).strip()
                for s in skills_data
                if isinstance(s, dict) and str(s.get("name", "")).strip()
            ]
        except Exception as exc:
            logger.warning("Certificate skill extraction failed: %s", exc)

        return [
            CertificateDraft(
                title=parsed_doc["title"],
                issuer="",
                issued_at=None,
                validated_skills=skills,
            )
        ]
