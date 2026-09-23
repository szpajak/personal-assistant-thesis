from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.kg.graphrag import GraphRAG
from app.kg.ingestion import KGIngestion
from app.kg.repository import KGRepository
from app.pipelines.skill_analysis_pipeline import (
    LearningRoadmapPipeline,
    SkillAnalysisPipeline,
)


@pytest.fixture
def mock_kg_ingestion() -> AsyncMock:
    return AsyncMock(spec=KGIngestion)


@pytest.fixture
def skill_analysis_pipeline(
    kg_repository: KGRepository, graph_rag: GraphRAG, mock_kg_ingestion: AsyncMock
) -> SkillAnalysisPipeline:
    return SkillAnalysisPipeline(
        kg_repository=kg_repository, graph_rag=graph_rag, kg_ingestion=mock_kg_ingestion
    )


@pytest.fixture
def learning_roadmap_pipeline(
    kg_repository: KGRepository, graph_rag: GraphRAG, mock_kg_ingestion: AsyncMock
) -> LearningRoadmapPipeline:
    return LearningRoadmapPipeline(
        kg_repository=kg_repository, graph_rag=graph_rag, kg_ingestion=mock_kg_ingestion
    )


@pytest.mark.asyncio
async def test_market_variant_computes_hard_gaps_without_llm_or_graphrag(
    skill_analysis_pipeline: SkillAnalysisPipeline,
    kg_repository: KGRepository,
    graph_rag: GraphRAG,
) -> None:
    """Market variant (no target_role_id): pure Cypher demand aggregate,
    hard gaps computed in Python - no LLM, no GraphRAG call at all."""
    user_id = "user_123"

    with patch.object(
        kg_repository, "get_person_skills", new_callable=AsyncMock
    ) as mock_skills:
        mock_skills.return_value = [
            {"name": "Python", "level": "advanced"},
            {"name": "FastAPI", "level": "intermediate"},
        ]

        with patch.object(kg_repository, "query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [
                {"name": "Python", "demand": 8, "levels": ["advanced"] * 5},
                {"name": "AWS", "demand": 5, "levels": ["advanced", "advanced", None]},
                {"name": "Docker", "demand": 3, "levels": [None]},
            ]

            with patch.object(
                graph_rag, "retrieve", new_callable=AsyncMock
            ) as mock_retrieve:
                result = await skill_analysis_pipeline.run(user_id)

            mock_retrieve.assert_not_called()

    assert result["target_role_ready"] is True
    assert "Python" in result["core_strengths"]
    gap_by_name = {g["skill"]: g for g in result["skill_gaps"]}
    assert gap_by_name["AWS"]["kind"] == "missing"
    assert gap_by_name["AWS"]["demand"] == 5
    assert gap_by_name["AWS"]["expected_level"] == "advanced"
    assert gap_by_name["Docker"]["kind"] == "missing"
    assert gap_by_name["Docker"]["demand"] == 3
    assert "Python" not in gap_by_name

    mock_skills.assert_called_once()
    mock_query.assert_called_once()


@pytest.mark.asyncio
async def test_detects_underleveled_skill(
    skill_analysis_pipeline: SkillAnalysisPipeline,
    kg_repository: KGRepository,
) -> None:
    """A skill the candidate has, but below the typical REQUIRES.level
    across postings, is a hard gap of kind 'underleveled', not 'missing'."""
    user_id = "user_123"

    with patch.object(
        kg_repository, "get_person_skills", new_callable=AsyncMock
    ) as mock_skills:
        mock_skills.return_value = [{"name": "Python", "level": "beginner"}]

        with patch.object(kg_repository, "query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [
                {
                    "name": "Python",
                    "demand": 10,
                    "levels": ["advanced"] * 8 + ["intermediate"] * 2,
                },
            ]

            result = await skill_analysis_pipeline.run(user_id)

    gap = result["skill_gaps"][0]
    assert gap["skill"] == "Python"
    assert gap["kind"] == "underleveled"
    assert gap["current_level"] == "beginner"
    assert gap["expected_level"] == "advanced"
    assert gap["demand"] == 10


@pytest.mark.asyncio
async def test_target_role_ready_aggregates_over_sampled_jobs(
    skill_analysis_pipeline: SkillAnalysisPipeline,
    kg_repository: KGRepository,
    graph_rag: GraphRAG,
) -> None:
    """Ready target role: demand/gaps come from
    ``get_target_role_sample_stats`` (the ~50 sampled JobOffers), not
    GraphRAG or the global market aggregate."""
    user_id = "user_123"
    target_role_id = "target_role_senior_devops"

    with patch.object(
        kg_repository, "get_person_skills", new_callable=AsyncMock
    ) as mock_skills:
        mock_skills.return_value = [{"name": "Docker", "level": "intermediate"}]

        with patch.object(kg_repository, "query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [
                {
                    "title": "Senior DevOps Engineer",
                    "sample_status": "ready",
                    "sample_job_count": 48,
                }
            ]

            with patch.object(
                kg_repository, "get_target_role_sample_stats", new_callable=AsyncMock
            ) as mock_stats:
                mock_stats.return_value = [
                    {"name": "Kubernetes", "demand": 30, "levels": ["advanced"] * 20},
                    {"name": "Docker", "demand": 25, "levels": ["advanced"] * 15},
                ]

                with patch.object(
                    graph_rag, "retrieve", new_callable=AsyncMock
                ) as mock_retrieve:
                    result = await skill_analysis_pipeline.run(
                        user_id, target_role_id=target_role_id
                    )

                mock_retrieve.assert_not_called()
                mock_stats.assert_awaited_once_with(target_role_id)

    assert result["target_role_ready"] is True
    assert result["target_role_title"] == "Senior DevOps Engineer"
    assert result["sample_status"] == "ready"
    assert result["sample_job_count"] == 48
    gap_by_name = {g["skill"]: g for g in result["skill_gaps"]}
    assert gap_by_name["Kubernetes"]["kind"] == "missing"
    # Docker: candidate has it but underleveled vs. the sample's "advanced".
    assert gap_by_name["Docker"]["kind"] == "underleveled"


@pytest.mark.asyncio
async def test_target_role_not_ready_surfaces_status_without_fake_gaps(
    skill_analysis_pipeline: SkillAnalysisPipeline,
    kg_repository: KGRepository,
) -> None:
    """A role whose sample hasn't finished (or failed) yields no gaps and
    no fallback to unrelated KG jobs - just the current sample status."""
    user_id = "user_123"
    target_role_id = "target_role_rare"

    with patch.object(
        kg_repository, "get_person_skills", new_callable=AsyncMock
    ) as mock_skills:
        mock_skills.return_value = []

        with patch.object(kg_repository, "query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [
                {
                    "title": "Rare Role",
                    "sample_status": "scraping",
                    "sample_job_count": 0,
                }
            ]

            result = await skill_analysis_pipeline.run(
                user_id, target_role_id=target_role_id
            )

    assert result["target_role_ready"] is False
    assert result["sample_status"] == "scraping"
    assert result["skill_gaps"] == []


@pytest.mark.asyncio
async def test_target_role_missing_reports_not_ready(
    skill_analysis_pipeline: SkillAnalysisPipeline,
    kg_repository: KGRepository,
) -> None:
    """A deleted/unknown TargetRole id is not-ready with no title, rather
    than silently falling back to the global market."""
    user_id = "user_123"

    with patch.object(
        kg_repository, "get_person_skills", new_callable=AsyncMock
    ) as mock_skills:
        mock_skills.return_value = []

        with patch.object(kg_repository, "query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = []

            result = await skill_analysis_pipeline.run(
                user_id, target_role_id="missing_role"
            )

    assert result["target_role_ready"] is False
    assert result["target_role_title"] is None
    assert result["skill_gaps"] == []


@pytest.mark.asyncio
async def test_learning_roadmap_generates_and_persists_phases(
    learning_roadmap_pipeline: LearningRoadmapPipeline,
    kg_repository: KGRepository,
    mock_kg_ingestion: AsyncMock,
) -> None:
    """Market-mode roadmap: LLM output is normalized into phases and each
    phase is persisted as a LearningResource."""
    user_id = "user_123"

    with patch.object(
        kg_repository, "get_person_career_brief", new_callable=AsyncMock
    ) as mock_brief:
        mock_brief.return_value = {}

        mock_response = AIMessage(
            content=(
                '{"overview": "Focused roadmap.", "overall_duration": "6-8 weeks", '
                '"phases": [{"title": "Phase 1: AWS foundations", "duration": "2 weeks", '
                '"goal": "Get comfortable with core AWS services.", '
                '"concepts": ["IAM basics", "EC2 fundamentals"], '
                '"steps": ["Deploy a VM", "Configure IAM roles"], "project_title": null}]}'
            )
        )
        with patch(
            "langchain_deepseek.ChatDeepSeek.ainvoke", return_value=mock_response
        ):
            roadmap = await learning_roadmap_pipeline.generate(user_id, skills=["AWS"])

    assert roadmap["overall_duration"] == "6-8 weeks"
    assert len(roadmap["phases"]) == 1
    assert roadmap["phases"][0]["concepts"] == ["IAM basics", "EC2 fundamentals"]
    mock_kg_ingestion.ingest_learning_resource.assert_called_once()


@pytest.mark.asyncio
async def test_learning_roadmap_target_role_uses_scoped_graphrag(
    learning_roadmap_pipeline: LearningRoadmapPipeline,
    kg_repository: KGRepository,
    graph_rag: GraphRAG,
    mock_kg_ingestion: AsyncMock,
) -> None:
    """Target-role roadmap grounds the prompt in a GraphRAG retrieval
    scoped to exactly that role's sampled JobOffer ids."""
    user_id = "user_123"
    target_role_id = "target_role_senior_devops"

    with patch.object(
        kg_repository, "get_person_career_brief", new_callable=AsyncMock
    ) as mock_brief:
        mock_brief.return_value = {}

        with patch.object(kg_repository, "query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [{"title": "Senior DevOps Engineer"}]

            with patch.object(
                kg_repository, "get_target_role_sample_job_ids", new_callable=AsyncMock
            ) as mock_job_ids:
                mock_job_ids.return_value = ["job_1", "job_2"]

                with patch.object(
                    graph_rag, "retrieve_scoped", new_callable=AsyncMock
                ) as mock_retrieve_scoped:
                    mock_retrieve_scoped.return_value = [
                        {
                            "node": {
                                "title": "Senior DevOps Engineer",
                                "company": "Acme",
                                "required_skills": ["Kubernetes", "Terraform"],
                            }
                        }
                    ]

                    mock_response = AIMessage(
                        content=(
                            '{"overview": "Role-specific roadmap.", "overall_duration": "8 weeks", '
                            '"phases": [{"title": "Phase 1", "duration": "2 weeks", "goal": "g", '
                            '"concepts": ["Kubernetes basics"], "steps": ["Deploy a cluster"], '
                            '"project_title": null}]}'
                        )
                    )
                    with patch(
                        "langchain_deepseek.ChatDeepSeek.ainvoke",
                        return_value=mock_response,
                    ):
                        roadmap = await learning_roadmap_pipeline.generate(
                            user_id,
                            skills=["Kubernetes"],
                            target_role_id=target_role_id,
                        )

                    mock_retrieve_scoped.assert_awaited_once()
                    call_kwargs = mock_retrieve_scoped.await_args.kwargs
                    assert call_kwargs["node_ids"] == ["job_1", "job_2"]

    assert roadmap["overview"] == "Role-specific roadmap."


@pytest.mark.asyncio
async def test_learning_roadmap_falls_back_when_llm_fails(
    learning_roadmap_pipeline: LearningRoadmapPipeline,
    kg_repository: KGRepository,
    mock_kg_ingestion: AsyncMock,
) -> None:
    """A parse/LLM failure still returns a deterministic roadmap instead
    of raising, so the UI always has something to show."""
    user_id = "user_123"

    with patch.object(
        kg_repository, "get_person_career_brief", new_callable=AsyncMock
    ) as mock_brief:
        mock_brief.return_value = {}

        with patch(
            "langchain_deepseek.ChatDeepSeek.ainvoke", side_effect=RuntimeError("boom")
        ):
            roadmap = await learning_roadmap_pipeline.generate(
                user_id, skills=["Rust", "WASM"]
            )

    assert len(roadmap["phases"]) >= 1
    assert "Rust" in roadmap["overview"] or "WASM" in roadmap["overview"]
