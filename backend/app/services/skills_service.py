"""Service for managing skills."""

from __future__ import annotations

import logging
from typing import Any

from ..db.generation_cache_repository import GenerationCacheRepository
from ..kg.repository import KGRepository
from ..pipelines.skill_analysis_pipeline import (
    LearningRoadmapPipeline,
    SkillAnalysisPipeline,
)
from ..schemas.skills import SkillCreate, SkillDemand, SkillRead
from ..utils.skill_ids import canonical_skill_id, resolve_canonical_skill_name

logger = logging.getLogger(__name__)

_SUGGESTED_PROJECTS_KIND = "suggested_projects"
_SUGGESTED_PROJECTS_SUBJECT = "default"
_SUGGESTED_PROJECTS_FINGERPRINT = "persistent"
_LEARNING_ROADMAP_KIND = "learning_roadmap"


class SkillsService:
    """Manage skills in the KG."""

    def __init__(
        self,
        kg_repository: KGRepository,
        skill_analysis_pipeline: SkillAnalysisPipeline,
        learning_roadmap_pipeline: LearningRoadmapPipeline | None = None,
        generation_cache_repository: GenerationCacheRepository | None = None,
    ) -> None:
        self.kg_repository = kg_repository
        self.skill_analysis_pipeline = skill_analysis_pipeline
        self.learning_roadmap_pipeline = learning_roadmap_pipeline
        self.generation_cache_repository = generation_cache_repository

    async def _persist_suggested_projects(
        self,
        person_id: str,
        projects: list[dict[str, Any]],
        skills: list[str] | None = None,
    ) -> None:
        """Store suggested projects so they survive container restarts."""
        if self.generation_cache_repository is None:
            return
        await self.generation_cache_repository.upsert(
            person_id=person_id,
            kind=_SUGGESTED_PROJECTS_KIND,
            subject_id=_SUGGESTED_PROJECTS_SUBJECT,
            profile_fingerprint=_SUGGESTED_PROJECTS_FINGERPRINT,
            payload_json={
                "suggested_projects": projects,
                "skills": list(skills or []),
            },
        )

    async def get_cached_suggested_projects(
        self,
        person_id: str,
    ) -> dict[str, Any]:
        """Return last persisted project suggestions, if any."""
        empty: dict[str, Any] = {
            "suggested_projects": [],
            "skills": [],
            "cached": False,
        }
        if self.generation_cache_repository is None:
            return empty
        row = await self.generation_cache_repository.get(
            person_id=person_id,
            kind=_SUGGESTED_PROJECTS_KIND,
            subject_id=_SUGGESTED_PROJECTS_SUBJECT,
        )
        if row is None or not isinstance(row.payload_json, dict):
            return empty
        projects = row.payload_json.get("suggested_projects") or []
        skills = row.payload_json.get("skills") or []
        if not isinstance(projects, list):
            projects = []
        if not isinstance(skills, list):
            skills = []
        return {
            "suggested_projects": projects,
            "skills": [str(s) for s in skills if isinstance(s, str) and s.strip()],
            "cached": True,
        }

    async def create_skill(
        self,
        person_id: str,
        payload: SkillCreate,
    ) -> SkillRead:
        """Create a new skill for a person."""
        try:
            skill_id = canonical_skill_id(payload.name)
            resolved_name = resolve_canonical_skill_name(payload.name)

            existing = await self.kg_repository.get_node("Skill", skill_id)
            existing_aliases = {
                str(a).strip()
                for a in (existing or {}).get("aliases", [])
                if str(a).strip()
            }
            if payload.name.strip().lower() != resolved_name.strip().lower():
                existing_aliases.add(payload.name.strip())

            skill_properties = {
                "id": skill_id,
                "name": resolved_name,
                "category": payload.category,
                "level": payload.level,
                "aliases": sorted(existing_aliases),
            }

            await self.kg_repository.upsert_node("Skill", skill_properties)

            await self.kg_repository.upsert_relationship(
                from_label="Person",
                from_id=person_id,
                relationship_type="HAS_SKILL",
                to_label="Skill",
                to_id=skill_id,
            )

            logger.info(f"Created skill {skill_id} for person {person_id}")

            return SkillRead(
                id=skill_id,
                name=resolved_name,
                category=payload.category,
                level=payload.level,
            )

        except Exception as e:
            logger.error(f"Failed to create skill: {e}")
            raise

    async def list_skills(
        self,
        person_id: str,
    ) -> list[SkillRead]:
        """List all skills for a person."""
        try:
            # Repair legacy finished projects that had USES but never got
            # HAS_SKILL (idempotent MERGE).
            try:
                await self.kg_repository.ensure_has_skill_for_finished_projects(
                    person_id
                )
            except Exception as repair_error:
                logger.warning(
                    "Finished-project HAS_SKILL repair skipped: %s", repair_error
                )

            skills = await self.kg_repository.get_person_skills(person_id)

            return [
                SkillRead(
                    id=s.get("id", ""),
                    name=s.get("name", ""),
                    category=s.get("category", ""),
                    level=s.get("level", ""),
                )
                for s in skills
            ]

        except Exception as e:
            logger.error(f"Failed to list skills: {e}")
            return []

    async def get_skill_gap_analysis(
        self,
        person_id: str,
        target_role_id: str | None = None,
    ) -> dict[str, Any]:
        """Deterministic skill-gap analysis (no LLM, no caching needed -
        see :class:`SkillAnalysisPipeline`): global market demand, or a
        specific :class:`TargetRole`'s sampled-postings demand.
        """
        try:
            return await self.skill_analysis_pipeline.run(
                user_id=person_id, target_role_id=target_role_id
            )
        except Exception as e:
            logger.error(f"Failed to compute skill gap analysis: {e}")
            return {
                "core_strengths": [],
                "skill_gaps": [],
                "target_role_ready": False,
                "target_role_title": None,
                "sample_status": None,
                "sample_job_count": 0,
                "error": str(e),
            }

    async def suggest_projects(
        self,
        person_id: str,
        skills: list[str],
    ) -> list[dict[str, Any]]:
        """Generate portfolio projects covering an explicit skill list."""
        projects = await self.skill_analysis_pipeline.suggest_projects_for_skills(
            user_id=person_id,
            skills=skills,
        )
        await self._persist_suggested_projects(person_id, projects, skills=skills)
        return projects

    async def generate_learning_roadmap(
        self,
        person_id: str,
        skills: list[str],
        target_role_id: str | None = None,
        included_projects: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Generate a phased learning roadmap for an explicit skill set,
        optionally scheduling already-chosen suggested projects into it.
        """
        if self.learning_roadmap_pipeline is None:
            raise RuntimeError("Learning roadmap pipeline is not configured")
        roadmap = await self.learning_roadmap_pipeline.generate(
            user_id=person_id,
            skills=skills,
            target_role_id=target_role_id,
            included_projects=included_projects or [],
        )
        if self.generation_cache_repository is not None:
            await self.generation_cache_repository.upsert(
                person_id=person_id,
                kind=_LEARNING_ROADMAP_KIND,
                subject_id=_SUGGESTED_PROJECTS_SUBJECT,
                profile_fingerprint=_SUGGESTED_PROJECTS_FINGERPRINT,
                payload_json={"roadmap": roadmap},
            )
        return roadmap

    async def get_cached_learning_roadmap(self, person_id: str) -> dict[str, Any]:
        """Return the last generated learning roadmap, if any."""
        empty: dict[str, Any] = {"roadmap": None, "cached": False}
        if self.generation_cache_repository is None:
            return empty
        row = await self.generation_cache_repository.get(
            person_id=person_id,
            kind=_LEARNING_ROADMAP_KIND,
            subject_id=_SUGGESTED_PROJECTS_SUBJECT,
        )
        if row is None or not isinstance(row.payload_json, dict):
            return empty
        roadmap = row.payload_json.get("roadmap")
        if not isinstance(roadmap, dict):
            return empty
        return {"roadmap": roadmap, "cached": True}

    async def get_market_demand(
        self,
        person_id: str,
        target_role_id: str | None = None,
        limit: int = 10,
    ) -> list[SkillDemand]:
        """Top skills required in the market: globally across career
        offers, or (when ``target_role_id`` is set) over that role's
        sampled postings - see plan section 2. Marks each skill the person
        already has as ``is_owned`` instead of treating everything as a
        gap to learn.
        """
        try:
            if target_role_id:
                results = await self.kg_repository.get_target_role_sample_stats(
                    target_role_id
                )
                results = results[:limit]
            else:
                results = await self.kg_repository.get_market_demand(limit=limit)

            owned_skills = {
                str(s.get("name") or "").strip().lower()
                for s in await self.kg_repository.get_person_skills(person_id)
                if s.get("name")
            }
            return [
                SkillDemand(
                    name=r["name"],
                    demand=r.get("demand") or 0,
                    is_owned=str(r.get("name") or "").strip().lower() in owned_skills,
                )
                for r in results
                if r.get("name")
            ]
        except Exception as e:
            logger.error(f"Failed to get market demand: {e}")
            return []
