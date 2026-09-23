"""Service for managing portfolio projects."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from ..kg.chains import create_project_enrichment_chain, create_project_extraction_chain
from ..kg.ingestion import KGIngestion
from ..kg.repository import KGRepository
from ..schemas.portfolio import (
    ProjectCreate,
    ProjectDraft,
    ProjectRead,
    ProjectUpdate,
    PublicCertificate,
    PublicEducation,
    PublicEmployment,
    PublicPortfolioExport,
    PublicSkill,
    SkillDraft,
    coerce_seniority,
)
from ..utils.llm_json import (
    extract_json_array_from_llm_output,
    extract_json_from_llm_output,
)
from ..utils.parsing import DocumentParser, truncate_document_text

logger = logging.getLogger(__name__)


def _parse_iso_date(value: Any) -> date | None:
    """Best-effort parse of an LLM-returned date string."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _safe_skill_draft(skill: dict[str, Any]) -> SkillDraft | None:
    """Build a SkillDraft from a raw LLM dict, skipping it (with a warning)
    on any unexpected validation error instead of failing the whole request.

    SkillDraft.category already coerces unrecognized-but-string values (e.g.
    "library" -> "framework"), so this mainly guards against malformed
    confidence values or other unexpected shapes in noisy LLM output.
    """
    try:
        return SkillDraft(
            name=str(skill.get("name", "")),
            canonical_name=skill.get("canonical_name"),
            category=skill.get("category", "technical"),
            level=skill.get("level", "intermediate"),
            confidence=float(skill.get("confidence", 0.8)),
        )
    except (TypeError, ValueError) as exc:
        logger.warning("Skipping malformed skill draft %r: %s", skill, exc)
        return None


class PortfolioService:
    """Manage portfolio projects in the KG."""

    def __init__(
        self,
        kg_repository: KGRepository,
        kg_ingestion: KGIngestion,
    ) -> None:
        """Initialize portfolio service.

        Args:
            kg_repository: Knowledge graph repository
            kg_ingestion: KG ingestion service

        """
        self.kg_repository = kg_repository
        self.kg_ingestion = kg_ingestion

    async def create_project(
        self,
        person_id: str,
        project: ProjectCreate,
    ) -> ProjectRead:
        """Create a new portfolio project.

        Skill *levels* are always taken from the caller (the form lets the
        user self-assess each skill's proficiency; a confirmed upload draft
        carries the level the user reviewed/edited) and are never touched by
        enrichment. If the caller did not already supply classified skills, a
        light LLM enrichment pass classifies them into categories, may add
        skills implied by the description (with an LLM-assessed level, since
        the user never saw those), and assesses the project's seniority.
        Callers that already hold a confirmed draft (e.g. from a document
        upload) set ``skip_enrichment=True`` to avoid a second LLM call.

        Args:
            person_id: Person/owner ID
            project: Project creation payload

        Returns:
            Created project

        """
        try:
            # Ensure the person node exists in KG (lazy creation)
            await self.kg_repository.upsert_node("Person", {"id": person_id})

            skills_payload: list[dict[str, Any]] = [
                s.model_dump() for s in project.skills
            ]
            seniority = project.seniority

            if not project.skip_enrichment:
                # Back-compat: older/plain callers (e.g. create_project_from_plan)
                # may only supply tech_stack, with no per-skill level. Seed those
                # with the "intermediate" default rather than skipping enrichment.
                seed_skills = skills_payload or [
                    {"name": tech, "level": "intermediate"}
                    for tech in project.tech_stack
                ]
                enriched_skills, enriched_seniority = await self._enrich_project(
                    title=project.title,
                    description=project.description,
                    skills=seed_skills,
                )
                if enriched_skills:
                    skills_payload = enriched_skills
                if seniority is None:
                    seniority = enriched_seniority

            # skip_enrichment is only set by the upload-confirm flow (the form
            # always sends False), so it doubles as a provenance marker for the
            # USES/HAS_SKILL relationship metadata.
            source = "upload" if project.skip_enrichment else "form"

            # Ingest project into KG and get its generated ID
            project_id = await self.kg_ingestion.ingest_project(
                title=project.title,
                description=project.description,
                tech_stack=project.tech_stack,
                metadata={
                    "start_date": project.start_date,
                    "end_date": project.end_date,
                    "url": "",
                    "media_urls": project.media_urls,
                    "seniority": seniority,
                    "achievements": project.achievements,
                    "status": project.status,
                    "source": source,
                },
                person_id=person_id,
                skills=skills_payload,
            )

            # Link project to person
            await self.kg_repository.upsert_relationship(
                from_label="Person",
                from_id=person_id,
                relationship_type="PRODUCED",
                to_label="Project",
                to_id=project_id,
            )

            # After PRODUCED exists, finished projects grant HAS_SKILL for
            # their USES skills (idempotent ON CREATE — won't clobber certs).
            if project.status == "finished":
                await self.kg_repository.ensure_has_skill_for_finished_projects(
                    person_id, project_id=project_id
                )

            logger.info(f"Created project {project_id} for person {person_id}")

            final_tech_stack = project.tech_stack or [
                str(s.get("canonical_name") or s.get("name", ""))
                for s in skills_payload
            ]

            return ProjectRead(
                id=project_id,
                title=project.title,
                description=project.description,
                tech_stack=final_tech_stack,
                start_date=project.start_date,
                end_date=project.end_date,
                media_urls=project.media_urls,
                seniority=seniority,
                achievements=project.achievements,
                skills=[SkillDraft(**s) for s in skills_payload],
                skip_enrichment=project.skip_enrichment,
                status=project.status,
            )

        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            raise

    async def _enrich_project(
        self,
        title: str,
        description: str,
        skills: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Classify user-supplied skills into categories and assess seniority.

        ``skills`` items carry a user-set (or default) ``level`` that is
        self-assessed proficiency and must NEVER be changed here - only
        ``category`` is classified by the LLM. The LLM may also propose
        additional skills implied by the description that the user didn't
        list; those DO get an LLM-assessed level, since the user never saw
        them. Never touches title/description/dates either.

        On any failure, falls back to the given skills as-is (default
        category, original levels preserved) rather than losing them.
        """
        user_levels = {
            str(skill.get("name", "")).strip().lower(): skill.get(
                "level", "intermediate"
            )
            for skill in skills
            if str(skill.get("name", "")).strip()
        }
        skills_text = (
            ", ".join(
                f"{skill.get('name')} (level: {skill.get('level', 'intermediate')})"
                for skill in skills
                if str(skill.get("name", "")).strip()
            )
            or "(none specified)"
        )

        try:
            chain = create_project_enrichment_chain()
            response = await chain.ainvoke(
                {
                    "title": title,
                    "description": description,
                    "skills": skills_text,
                }
            )
            result = extract_json_from_llm_output(str(response.content))
            raw_skills = [
                skill
                for skill in result.get("skills", [])
                if isinstance(skill, dict) and str(skill.get("name", "")).strip()
            ]

            merged: list[dict[str, Any]] = []
            seen_names: set[str] = set()
            for skill in raw_skills:
                name_key = str(skill.get("name", "")).strip().lower()
                if name_key in user_levels:
                    # Defensive: never trust the LLM with a user-set level,
                    # even though the prompt instructs it not to change it.
                    skill = {**skill, "level": user_levels[name_key]}
                draft = _safe_skill_draft(skill)
                if draft is not None:
                    merged.append(draft.model_dump())
                    seen_names.add(name_key)

            # Make sure every user-listed skill survives even if the LLM
            # dropped it from its response.
            for skill in skills:
                name = str(skill.get("name", "")).strip()
                name_key = name.lower()
                if not name or name_key in seen_names:
                    continue
                draft = _safe_skill_draft(
                    {
                        "name": name,
                        "level": skill.get("level", "intermediate"),
                        "category": "technical",
                        "confidence": 1.0,
                    }
                )
                if draft is not None:
                    merged.append(draft.model_dump())

            seniority = coerce_seniority(result.get("seniority"))
            return merged, seniority
        except Exception as exc:
            logger.warning(
                "Project enrichment failed, using given skills as-is: %s", exc
            )
            fallback = [
                draft.model_dump()
                for draft in (
                    _safe_skill_draft(
                        {
                            "name": skill.get("name", ""),
                            "level": skill.get("level", "intermediate"),
                            "category": "technical",
                            "confidence": 1.0,
                        }
                    )
                    for skill in skills
                    if str(skill.get("name", "")).strip()
                )
                if draft is not None
            ]
            return fallback, None

    async def extract_project_drafts(self, file_path: str) -> list[ProjectDraft]:
        """Parse a document and extract project drafts for user review.

        This performs the heavy LLM extraction only - nothing is written to
        the knowledge graph. The caller (API layer) returns the drafts to the
        frontend, which lets the user edit and confirm before each draft is
        submitted as a ``ProjectCreate`` (with ``skip_enrichment=True``) via
        the normal create endpoint.

        Args:
            file_path: Path to the document to parse

        Returns:
            List of extracted project drafts (may describe multiple projects,
            e.g. when uploading a full CV)

        """
        try:
            parser = DocumentParser()
            parsed_doc = await parser.parse_file(file_path)

            chain = create_project_extraction_chain()
            response = await chain.ainvoke(
                {"text": truncate_document_text(parsed_doc["text"])}
            )

            try:
                extracted = extract_json_array_from_llm_output(str(response.content))
            except (ValueError, AttributeError) as exc:
                logger.warning(
                    "Failed to parse LLM extraction response, falling back to basic info: %s",
                    exc,
                )
                extracted = [
                    {
                        "title": parsed_doc["title"],
                        "description": parsed_doc["text"][:500],
                        "skills": [],
                    }
                ]

            drafts = [
                self._draft_from_extraction(item, fallback_title=parsed_doc["title"])
                for item in extracted
                if isinstance(item, dict)
            ]

            if not drafts:
                drafts.append(
                    ProjectDraft(
                        title=parsed_doc["title"],
                        description=parsed_doc["text"][:500],
                        source="upload",
                    )
                )

            return drafts

        except Exception as e:
            logger.error(f"Failed to extract project drafts: {e}")
            raise

    def _draft_from_extraction(
        self,
        item: dict[str, Any],
        fallback_title: str,
    ) -> ProjectDraft:
        """Map one raw LLM extraction object into a validated ProjectDraft."""
        skills = [
            draft
            for draft in (
                _safe_skill_draft(skill)
                for skill in item.get("skills", [])
                if isinstance(skill, dict) and str(skill.get("name", "")).strip()
            )
            if draft is not None
        ]

        return ProjectDraft(
            title=str(item.get("title") or fallback_title),
            description=str(item.get("description", "")),
            skills=skills,
            tech_stack=[str(s.canonical_name or s.name) for s in skills],
            start_date=_parse_iso_date(item.get("start_date")),
            end_date=_parse_iso_date(item.get("end_date")),
            achievements=[str(a) for a in item.get("achievements", []) if a],
            seniority=coerce_seniority(item.get("seniority")),
            source="upload",
        )

    async def create_project_from_plan(
        self,
        person_id: str,
        item: dict[str, Any],
    ) -> ProjectRead:
        """Create a planned/in-progress project from a learning plan item."""
        try:
            skill_name = item.get("skill_name")
            tech_stack = [str(skill_name)] if skill_name else []

            project = ProjectCreate(
                title=item.get("title", "New Learning Project"),
                description=(
                    f"Learning project based on suggested resource: "
                    f"{item.get('description', '')}\n\nURL: {item.get('url', 'N/A')}"
                ),
                tech_stack=tech_stack,
                start_date=date.today(),
                end_date=None,
                status="planned",
            )
            return await self.create_project(person_id, project)

        except Exception as e:
            logger.error(f"Failed to create project from plan: {e}")
            raise

    async def create_project_from_suggestion(
        self,
        person_id: str,
        suggestion: dict[str, Any],
    ) -> ProjectRead:
        """Create a planned project from a multi-skill analysis suggestion."""
        try:
            skills_covered = [
                str(s) for s in (suggestion.get("skills_covered") or []) if s
            ]
            tech_stack = [str(t) for t in (suggestion.get("tech_stack") or []) if t]
            if not tech_stack:
                tech_stack = list(skills_covered)

            description = str(suggestion.get("description") or "").strip()
            key_steps = [
                str(s).strip()
                for s in (suggestion.get("key_steps") or [])
                if str(s).strip()
            ]
            deliverables = [
                str(d).strip()
                for d in (suggestion.get("deliverables") or [])
                if str(d).strip()
            ]
            extras: list[str] = []
            if key_steps:
                extras.append(
                    "Key steps:\n"
                    + "\n".join(f"{i}. {step}" for i, step in enumerate(key_steps, 1))
                )
            if deliverables:
                extras.append(
                    "Deliverables:\n" + "\n".join(f"- {item}" for item in deliverables)
                )
            if extras:
                description = (
                    f"{description}\n\n" + "\n\n".join(extras)
                    if description
                    else "\n\n".join(extras)
                )

            project = ProjectCreate(
                title=str(suggestion.get("title") or "Suggested Portfolio Project"),
                description=description,
                tech_stack=tech_stack,
                skills=[
                    SkillDraft(name=skill, level="intermediate")
                    for skill in skills_covered or tech_stack
                ],
                start_date=date.today(),
                end_date=None,
                status="planned",
            )
            return await self.create_project(person_id, project)
        except Exception as e:
            logger.error(f"Failed to create project from suggestion: {e}")
            raise

    def _row_to_project_read(self, p: dict[str, Any]) -> ProjectRead:
        start_dt = p.get("start_date")
        if start_dt is not None and not isinstance(start_dt, date):
            try:
                start_dt = date.fromisoformat(str(start_dt))
            except (ValueError, TypeError):
                start_dt = None
        if start_dt is None:
            start_dt = date(1970, 1, 1)
        end_dt = p.get("end_date")
        if end_dt is not None and not isinstance(end_dt, date):
            try:
                end_dt = date.fromisoformat(str(end_dt))
            except (ValueError, TypeError):
                end_dt = None
        status = str(p.get("status") or "in_progress")
        if status not in {"planned", "in_progress", "finished"}:
            status = "in_progress"
        return ProjectRead(
            id=p.get("id", ""),
            title=p.get("title", ""),
            description=p.get("description", ""),
            tech_stack=p.get("tech_stack", []) or [],
            start_date=start_dt,
            end_date=end_dt,
            media_urls=p.get("media_urls", []) or [],
            seniority=coerce_seniority(p.get("seniority")),
            achievements=p.get("achievements", []) or [],
            skip_enrichment=True,
            status=status,  # type: ignore[arg-type]
        )

    async def list_projects(
        self,
        person_id: str,
        status: str | None = None,
    ) -> list[ProjectRead]:
        """List portfolio projects for a person, optionally filtered by status."""
        try:
            projects = await self.kg_repository.find_related_nodes(
                start_label="Person",
                start_id=person_id,
                relationship_type="PRODUCED",
                hops=1,
            )

            result: list[ProjectRead] = []
            for p in projects:
                read = self._row_to_project_read(p)
                if status and read.status != status:
                    continue
                result.append(read)
            return result

        except Exception as e:
            logger.error(f"Failed to list projects: {e}")
            return []

    async def update_project(
        self,
        person_id: str,
        project_id: str,
        payload: ProjectUpdate,
    ) -> ProjectRead:
        """Update an existing project owned by the person."""
        existing = await self.kg_repository.get_node("Project", project_id)
        if not existing:
            raise ValueError(f"Project {project_id} not found")

        owned = await self.kg_repository.find_related_nodes(
            start_label="Person",
            start_id=person_id,
            relationship_type="PRODUCED",
            hops=1,
        )
        if not any(str(p.get("id")) == project_id for p in owned):
            raise ValueError(f"Project {project_id} not found for person {person_id}")

        updates = payload.model_dump(exclude_unset=True)
        if "skills" in updates:
            # Skills are relationship-backed; keep tech_stack as the editable list.
            updates.pop("skills", None)
        if "seniority" in updates:
            updates["seniority"] = coerce_seniority(updates.get("seniority"))

        merged = {**existing, **updates, "id": project_id}
        # Avoid writing large embedding blobs twice when untouched
        await self.kg_repository.upsert_node("Project", merged)

        new_status = str(merged.get("status") or "in_progress")
        # Finishing a project asserts skill acquisition → HAS_SKILL.
        # Demoting away from finished does not revoke HAS_SKILL (skills stay).
        if new_status == "finished":
            await self.kg_repository.ensure_has_skill_for_finished_projects(
                person_id, project_id=project_id
            )

        return self._row_to_project_read(merged)

    async def delete_project(self, person_id: str, project_id: str) -> bool:
        """Delete a project owned by the person. Returns False if missing."""
        owned = await self.kg_repository.find_related_nodes(
            start_label="Person",
            start_id=person_id,
            relationship_type="PRODUCED",
            hops=1,
        )
        if not any(str(p.get("id")) == project_id for p in owned):
            return False
        await self.kg_repository.delete_node("Project", project_id)
        return True

    async def export_public_portfolio(self, person_id: str) -> PublicPortfolioExport:
        """Build the public, read-only KG subset used to render the static
        portfolio site (backend/scripts/generate_portfolio_site.py) and
        served directly by ``GET /api/v1/portfolio/export/{person_id}``.

        Deliberately excludes anything private: Application, Email,
        LearningResource, raw embeddings, target roles. Planned projects are
        excluded too - they are to-do items, not evidence of finished/ongoing
        work.
        """
        person = await self.kg_repository.get_node("Person", person_id) or {}
        projects = [
            p for p in await self.list_projects(person_id) if p.status != "planned"
        ]

        skill_rows = await self.kg_repository.get_person_skills(person_id)
        skills = [
            PublicSkill(
                name=s.get("name", ""),
                category=s.get("category", "technical"),
                level=s.get("level", "intermediate"),
            )
            for s in skill_rows
            if s.get("name")
        ]

        cert_rows = await self.kg_repository.find_related_nodes(
            start_label="Person",
            start_id=person_id,
            relationship_type="HAS_CERTIFICATE",
            hops=1,
        )
        certificates = [
            PublicCertificate(
                title=c.get("title", ""),
                issuer=c.get("issuer", ""),
                issued_at=(
                    str(c["issued_at"]) if c.get("issued_at") is not None else None
                ),
            )
            for c in cert_rows
        ]

        employment_rows = await self.kg_repository.find_related_nodes(
            start_label="Person",
            start_id=person_id,
            relationship_type="WORKED_AT",
            hops=1,
        )
        employment = sorted(
            (
                PublicEmployment(
                    title=e.get("title", ""),
                    company=e.get("company", ""),
                    start_date=_parse_iso_date(e.get("start_date")),
                    end_date=_parse_iso_date(e.get("end_date")),
                    description=e.get("description", "") or "",
                    achievements=e.get("achievements", []) or [],
                )
                for e in employment_rows
            ),
            key=lambda e: e.start_date or date(1970, 1, 1),
            reverse=True,
        )

        education_rows = await self.kg_repository.find_related_nodes(
            start_label="Person",
            start_id=person_id,
            relationship_type="STUDIED_AT",
            hops=1,
        )
        education = sorted(
            (
                PublicEducation(
                    institution=e.get("institution", ""),
                    degree=e.get("degree", ""),
                    field_of_study=e.get("field_of_study", "") or "",
                    start_date=_parse_iso_date(e.get("start_date")),
                    end_date=_parse_iso_date(e.get("end_date")),
                    description=e.get("description", "") or "",
                )
                for e in education_rows
            ),
            key=lambda e: e.start_date or date(1970, 1, 1),
            reverse=True,
        )

        return PublicPortfolioExport(
            name=person.get("name", "Anonymous"),
            bio=person.get("bio", ""),
            email=person.get("email", "") or "",
            phone=person.get("phone", "") or "",
            location=person.get("location", "") or "",
            linkedin_url=person.get("linkedin_url", "") or "",
            github_url=person.get("github_url", "") or "",
            website_url=person.get("website_url", "") or "",
            awards=list(person.get("awards") or []),
            projects=projects,
            skills=skills,
            certificates=certificates,
            employment=employment,
            education=education,
        )
