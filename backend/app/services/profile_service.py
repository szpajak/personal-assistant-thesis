"""Service for career-chronology entities: Employment, Education, TargetRole."""

from __future__ import annotations

import logging
from datetime import date

from ..kg.chains import create_profile_extraction_chain
from ..kg.ingestion import KGIngestion
from ..kg.repository import KGRepository
from ..schemas.profile import (
    EducationCreate,
    EducationDraft,
    EducationRead,
    EducationUpdate,
    EmploymentCreate,
    EmploymentDraft,
    EmploymentRead,
    EmploymentUpdate,
    PersonProfileRead,
    PersonProfileUpdate,
    ProfileExtractResponse,
    ProfileSummary,
    TargetRoleCreate,
    TargetRoleRead,
    TargetRoleUpdate,
)
from ..utils.llm_json import extract_json_from_llm_output
from ..utils.parsing import DocumentParser, truncate_document_text

logger = logging.getLogger(__name__)


def _parse_iso_date(value: object) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


class ProfileService:
    """Manage career chronology (Employment/Education) and TargetRoles."""

    def __init__(
        self,
        kg_repository: KGRepository,
        kg_ingestion: KGIngestion,
    ) -> None:
        self.kg_repository = kg_repository
        self.kg_ingestion = kg_ingestion

    async def create_employment(
        self, person_id: str, payload: EmploymentCreate
    ) -> EmploymentRead:
        emp_id = await self.kg_ingestion.ingest_employment(
            person_id=person_id,
            title=payload.title,
            company=payload.company,
            start_date=payload.start_date.isoformat(),
            end_date=payload.end_date.isoformat() if payload.end_date else None,
            description=payload.description,
            achievements=payload.achievements,
            skills=payload.skills,
        )
        return EmploymentRead(id=emp_id, **payload.model_dump())

    async def list_employment(self, person_id: str) -> list[EmploymentRead]:
        try:
            rows = await self.kg_repository.find_related_nodes(
                start_label="Person",
                start_id=person_id,
                relationship_type="WORKED_AT",
                hops=1,
            )
            results = []
            for row in sorted(
                rows, key=lambda r: str(r.get("start_date") or ""), reverse=True
            ):
                start_dt = _parse_iso_date(row.get("start_date")) or date(1970, 1, 1)
                results.append(
                    EmploymentRead(
                        id=row.get("id", ""),
                        title=row.get("title", ""),
                        company=row.get("company", ""),
                        start_date=start_dt,
                        end_date=_parse_iso_date(row.get("end_date")),
                        description=row.get("description", ""),
                        achievements=row.get("achievements", []) or [],
                        skills=[],
                    )
                )
            return results
        except Exception as e:
            logger.error(f"Failed to list employment: {e}")
            return []

    async def create_education(
        self, person_id: str, payload: EducationCreate
    ) -> EducationRead:
        edu_id = await self.kg_ingestion.ingest_education(
            person_id=person_id,
            institution=payload.institution,
            degree=payload.degree,
            field_of_study=payload.field_of_study,
            start_date=payload.start_date.isoformat(),
            end_date=payload.end_date.isoformat() if payload.end_date else None,
            description=payload.description,
        )
        return EducationRead(id=edu_id, **payload.model_dump())

    async def list_education(self, person_id: str) -> list[EducationRead]:
        try:
            rows = await self.kg_repository.find_related_nodes(
                start_label="Person",
                start_id=person_id,
                relationship_type="STUDIED_AT",
                hops=1,
            )
            results = []
            for row in sorted(
                rows, key=lambda r: str(r.get("start_date") or ""), reverse=True
            ):
                start_dt = _parse_iso_date(row.get("start_date")) or date(1970, 1, 1)
                results.append(
                    EducationRead(
                        id=row.get("id", ""),
                        institution=row.get("institution", ""),
                        degree=row.get("degree", ""),
                        field_of_study=row.get("field_of_study", ""),
                        start_date=start_dt,
                        end_date=_parse_iso_date(row.get("end_date")),
                        description=row.get("description", ""),
                    )
                )
            return results
        except Exception as e:
            logger.error(f"Failed to list education: {e}")
            return []

    async def extract_profile_drafts(self, file_path: str) -> ProfileExtractResponse:
        """Parse a CV/resume document and extract employment/education
        drafts for user review. Nothing is written to the KG here.
        """
        parser = DocumentParser()
        parsed_doc = await parser.parse_file(file_path)

        try:
            chain = create_profile_extraction_chain()
            response = await chain.ainvoke(
                {"text": truncate_document_text(parsed_doc["text"])}
            )
            data = extract_json_from_llm_output(str(response.content))
        except Exception as exc:
            logger.warning("Profile chronology extraction failed: %s", exc)
            data = {}

        employment = [
            EmploymentDraft(
                title=str(item.get("title", "")),
                company=str(item.get("company", "")),
                start_date=_parse_iso_date(item.get("start_date")),
                end_date=_parse_iso_date(item.get("end_date")),
                description=str(item.get("description", "")),
                achievements=[str(a) for a in item.get("achievements", []) if a],
                skills=[str(s) for s in item.get("skills", []) if s],
            )
            for item in data.get("employment", [])
            if isinstance(item, dict) and str(item.get("title", "")).strip()
        ]
        education = [
            EducationDraft(
                institution=str(item.get("institution", "")),
                degree=str(item.get("degree", "")),
                field_of_study=str(item.get("field_of_study", "")),
                start_date=_parse_iso_date(item.get("start_date")),
                end_date=_parse_iso_date(item.get("end_date")),
                description=str(item.get("description", "")),
            )
            for item in data.get("education", [])
            if isinstance(item, dict) and str(item.get("institution", "")).strip()
        ]

        return ProfileExtractResponse(employment=employment, education=education)

    async def get_profile_details(self, person_id: str) -> PersonProfileRead:
        """Fetch the contact/header profile rendered on the generated CV."""
        person = await self.kg_repository.get_node("Person", person_id) or {}
        return PersonProfileRead(
            name=str(person.get("name") or ""),
            email=str(person.get("email") or ""),
            bio=str(person.get("bio") or ""),
            phone=str(person.get("phone") or ""),
            location=str(person.get("location") or ""),
            linkedin_url=str(person.get("linkedin_url") or ""),
            github_url=str(person.get("github_url") or ""),
            website_url=str(person.get("website_url") or ""),
            languages_spoken=str(person.get("languages_spoken") or ""),
            interests=str(person.get("interests") or ""),
            awards=list(person.get("awards") or []),
        )

    async def update_profile_details(
        self, person_id: str, payload: PersonProfileUpdate
    ) -> PersonProfileRead:
        """Partially update the contact/header profile. Only fields present in
        the payload are written; everything else is left untouched."""
        updates = payload.model_dump(exclude_unset=True)
        if updates:
            await self.kg_repository.upsert_node("Person", {"id": person_id, **updates})
        return await self.get_profile_details(person_id)

    async def create_target_role(
        self, person_id: str, payload: TargetRoleCreate
    ) -> TargetRoleRead:
        role_id = await self.kg_ingestion.ingest_target_role(
            person_id=person_id,
            title=payload.title,
            location=payload.location,
            country=payload.country,
        )
        return TargetRoleRead(
            id=role_id,
            title=payload.title,
            location=payload.location,
            country=payload.country,
        )

    def _row_to_target_role(self, row: dict) -> TargetRoleRead:
        return TargetRoleRead(
            id=row.get("id", ""),
            title=row.get("title", ""),
            location=row.get("location", "") or "",
            country=row.get("country", "") or "",
            required_skills=row.get("required_skills", []) or [],
            sample_status=row.get("sample_status") or "idle",
            sample_job_count=int(row.get("sample_job_count") or 0),
            last_sampled_at=row.get("last_sampled_at"),
        )

    async def list_target_roles(self, person_id: str) -> list[TargetRoleRead]:
        try:
            rows = await self.kg_repository.find_related_nodes(
                start_label="Person",
                start_id=person_id,
                relationship_type="AIMS_FOR",
                hops=1,
            )
            return [self._row_to_target_role(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to list target roles: {e}")
            return []

    async def get_target_role(
        self, person_id: str, role_id: str
    ) -> TargetRoleRead | None:
        owned = await self.list_target_roles(person_id)
        return next((r for r in owned if r.id == role_id), None)

    async def mark_target_role_sample_status(self, role_id: str, status: str) -> None:
        await self.kg_repository.upsert_node(
            "TargetRole", {"id": role_id, "sample_status": status}
        )

    async def update_employment(
        self, person_id: str, employment_id: str, payload: EmploymentUpdate
    ) -> EmploymentRead:
        owned = await self.list_employment(person_id)
        current = next((e for e in owned if e.id == employment_id), None)
        if not current:
            raise ValueError(f"Employment {employment_id} not found")
        updates = payload.model_dump(exclude_unset=True)
        merged = {**current.model_dump(), **updates, "id": employment_id}
        # Persist scalar fields; company/skills edges are set at create time.
        await self.kg_repository.upsert_node(
            "Employment",
            {
                "id": employment_id,
                "title": merged["title"],
                "company": merged["company"],
                "start_date": (
                    merged["start_date"].isoformat()
                    if isinstance(merged["start_date"], date)
                    else merged["start_date"]
                ),
                "end_date": (
                    merged["end_date"].isoformat()
                    if isinstance(merged.get("end_date"), date)
                    else merged.get("end_date")
                ),
                "description": merged.get("description") or "",
                "achievements": merged.get("achievements") or [],
            },
        )
        return EmploymentRead(**merged)

    async def delete_employment(self, person_id: str, employment_id: str) -> bool:
        owned = await self.list_employment(person_id)
        if not any(e.id == employment_id for e in owned):
            return False
        await self.kg_repository.delete_node("Employment", employment_id)
        return True

    async def update_education(
        self, person_id: str, education_id: str, payload: EducationUpdate
    ) -> EducationRead:
        owned = await self.list_education(person_id)
        current = next((e for e in owned if e.id == education_id), None)
        if not current:
            raise ValueError(f"Education {education_id} not found")
        updates = payload.model_dump(exclude_unset=True)
        merged = {**current.model_dump(), **updates, "id": education_id}
        await self.kg_repository.upsert_node(
            "Education",
            {
                "id": education_id,
                "institution": merged["institution"],
                "degree": merged["degree"],
                "field_of_study": merged.get("field_of_study") or "",
                "start_date": (
                    merged["start_date"].isoformat()
                    if isinstance(merged["start_date"], date)
                    else merged["start_date"]
                ),
                "end_date": (
                    merged["end_date"].isoformat()
                    if isinstance(merged.get("end_date"), date)
                    else merged.get("end_date")
                ),
                "description": merged.get("description") or "",
            },
        )
        return EducationRead(**merged)

    async def delete_education(self, person_id: str, education_id: str) -> bool:
        owned = await self.list_education(person_id)
        if not any(e.id == education_id for e in owned):
            return False
        await self.kg_repository.delete_node("Education", education_id)
        return True

    async def update_target_role(
        self, person_id: str, role_id: str, payload: TargetRoleUpdate
    ) -> TargetRoleRead:
        owned = await self.list_target_roles(person_id)
        current = next((r for r in owned if r.id == role_id), None)
        if not current:
            raise ValueError(f"Target role {role_id} not found")
        updates = payload.model_dump(exclude_unset=True)
        merged = {**current.model_dump(), **updates, "id": role_id}
        await self.kg_repository.upsert_node(
            "TargetRole",
            {
                "id": role_id,
                "title": merged["title"],
                "location": merged.get("location") or "",
                "country": merged.get("country") or "",
            },
        )
        return TargetRoleRead(**merged)

    async def delete_target_role(self, person_id: str, role_id: str) -> bool:
        owned = await self.list_target_roles(person_id)
        if not any(r.id == role_id for r in owned):
            return False
        await self.kg_repository.delete_node("TargetRole", role_id)
        return True

    async def get_summary(self, person_id: str) -> ProfileSummary:
        """Compute total years of experience by merging overlapping employments."""
        employment = await self.list_employment(person_id)
        education = await self.list_education(person_id)
        roles = await self.list_target_roles(person_id)

        today = date.today()
        ranges: list[tuple[date, date]] = []
        for emp in employment:
            start = emp.start_date
            end = emp.end_date or today
            if end < start:
                end = start
            ranges.append((start, end))
        ranges.sort(key=lambda r: r[0])

        merged: list[tuple[date, date]] = []
        for start, end in ranges:
            if not merged or start > merged[-1][1]:
                merged.append((start, end))
            else:
                prev_start, prev_end = merged[-1]
                merged[-1] = (prev_start, max(prev_end, end))

        total_days = sum((end - start).days for start, end in merged)
        years = round(total_days / 365.25, 1) if total_days else 0.0

        current = next((e for e in employment if e.end_date is None), None)
        if current is None and employment:
            current = employment[0]

        return ProfileSummary(
            total_years_experience=years,
            employment_count=len(employment),
            education_count=len(education),
            target_role_count=len(roles),
            current_title=current.title if current else None,
            current_company=current.company if current else None,
        )
