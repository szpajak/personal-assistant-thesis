from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.generation_cache_repository import GenerationCacheRepository
from ...dependencies import get_current_user, get_db_session
from ...kg.embeddings import KGEmbeddings
from ...kg.graphrag import GraphRAG
from ...kg.repository import KGRepository
from ...models.user import User
from ...pipelines.skill_analysis_pipeline import (
    LearningRoadmapPipeline,
    SkillAnalysisPipeline,
)
from ...schemas.skills import (
    LearningRoadmap,
    LearningRoadmapCache,
    LearningRoadmapRequest,
    SkillAnalysisResponse,
    SkillCreate,
    SkillDemand,
    SkillRead,
    SuggestedProject,
    SuggestedProjectsCache,
    SuggestedProjectsRequest,
)
from ...services.skills_service import SkillsService

router = APIRouter()


def get_skills_service(
    repo: KGRepository = Depends(),
    db: AsyncSession = Depends(get_db_session),
) -> SkillsService:
    embeddings = KGEmbeddings()
    graph_rag = GraphRAG(kg_repository=repo, embeddings=embeddings)
    pipeline = SkillAnalysisPipeline(kg_repository=repo, graph_rag=graph_rag)
    roadmap_pipeline = LearningRoadmapPipeline(kg_repository=repo, graph_rag=graph_rag)
    return SkillsService(
        kg_repository=repo,
        skill_analysis_pipeline=pipeline,
        learning_roadmap_pipeline=roadmap_pipeline,
        generation_cache_repository=GenerationCacheRepository(db=db),
    )


@router.get("/", response_model=list[SkillRead])
async def list_skills(
    current_user: User = Depends(get_current_user),
    service: SkillsService = Depends(get_skills_service),
) -> list[SkillRead]:
    person_id = f"user_{current_user.id}"
    skills: list[SkillRead] = await service.list_skills(person_id)
    return skills


@router.post("/", response_model=SkillRead)
async def add_skill(
    current_user: User = Depends(get_current_user),
    payload: SkillCreate = Body(...),
    service: SkillsService = Depends(get_skills_service),
) -> SkillRead:
    person_id = f"user_{current_user.id}"
    skill = await service.create_skill(person_id, payload)
    return skill


@router.get("/analysis", response_model=SkillAnalysisResponse)
async def get_skill_analysis(
    current_user: User = Depends(get_current_user),
    target_role_id: str | None = Query(
        None,
        description="Run gap analysis against this TargetRole instead of the market",
    ),
    service: SkillsService = Depends(get_skills_service),
) -> SkillAnalysisResponse:
    person_id = f"user_{current_user.id}"
    analysis = await service.get_skill_gap_analysis(
        person_id, target_role_id=target_role_id
    )
    return SkillAnalysisResponse.model_validate(analysis)


@router.get("/suggested-projects", response_model=SuggestedProjectsCache)
async def get_suggested_projects(
    current_user: User = Depends(get_current_user),
    service: SkillsService = Depends(get_skills_service),
) -> SuggestedProjectsCache:
    """Return last persisted suggested projects (no LLM call)."""
    person_id = f"user_{current_user.id}"
    cached = await service.get_cached_suggested_projects(person_id)
    return SuggestedProjectsCache.model_validate(cached)


@router.post("/suggested-projects", response_model=list[SuggestedProject])
async def suggest_projects(
    current_user: User = Depends(get_current_user),
    payload: SuggestedProjectsRequest = Body(...),
    service: SkillsService = Depends(get_skills_service),
) -> list[SuggestedProject]:
    """Regenerate portfolio project suggestions from a user-selected skill set."""
    person_id = f"user_{current_user.id}"
    skills = [s.strip() for s in payload.skills if isinstance(s, str) and s.strip()]
    if len(skills) < 2:
        raise HTTPException(
            status_code=400,
            detail="Select at least 2 skills to regenerate projects.",
        )
    try:
        projects = await service.suggest_projects(person_id, skills)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [SuggestedProject.model_validate(p) for p in projects]


@router.get("/market-demand", response_model=list[SkillDemand])
async def get_market_demand(
    current_user: User = Depends(get_current_user),
    limit: int = Query(10, description="Maximum number of skills to return"),
    target_role_id: str | None = Query(
        None,
        description=(
            "Aggregate demand over this TargetRole's sampled offers "
            "instead of the global market"
        ),
    ),
    service: SkillsService = Depends(get_skills_service),
) -> list[SkillDemand]:
    person_id = f"user_{current_user.id}"
    demand = await service.get_market_demand(
        person_id, target_role_id=target_role_id, limit=limit
    )
    return demand


@router.get("/learning-roadmap", response_model=LearningRoadmapCache)
async def get_learning_roadmap(
    current_user: User = Depends(get_current_user),
    service: SkillsService = Depends(get_skills_service),
) -> LearningRoadmapCache:
    """Return last generated learning roadmap (no LLM call)."""
    person_id = f"user_{current_user.id}"
    cached = await service.get_cached_learning_roadmap(person_id)
    return LearningRoadmapCache.model_validate(cached)


@router.post("/learning-roadmap", response_model=LearningRoadmap)
async def generate_learning_roadmap(
    current_user: User = Depends(get_current_user),
    payload: LearningRoadmapRequest = Body(...),
    service: SkillsService = Depends(get_skills_service),
) -> LearningRoadmap:
    """Generate a phased learning roadmap from the unified skill set,
    optionally scheduling already-chosen suggested projects into it."""
    person_id = f"user_{current_user.id}"
    skills = [s.strip() for s in payload.skills if isinstance(s, str) and s.strip()]
    if not skills:
        raise HTTPException(
            status_code=400, detail="Select at least 1 skill to generate a roadmap."
        )
    try:
        roadmap = await service.generate_learning_roadmap(
            person_id,
            skills=skills,
            target_role_id=payload.target_role_id,
            included_projects=[p.model_dump() for p in payload.included_projects],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return LearningRoadmap.model_validate(roadmap)
