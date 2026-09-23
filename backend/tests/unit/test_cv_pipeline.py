from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.kg.graphrag import GraphRAG
from app.kg.repository import KGRepository
from app.pipelines.cv_pipeline import CVPipeline


@pytest.fixture
def cv_pipeline(kg_repository: KGRepository, graph_rag: GraphRAG) -> CVPipeline:
    return CVPipeline(kg_repository=kg_repository, graph_rag=graph_rag)


def _project(pid: str, title: str, tech: list[str]) -> dict:
    return {
        "id": pid,
        "title": title,
        "tech_stack": tech,
        "start_date": "2020-01-01",
        "description": f"{title} description",
        "achievements": [],
    }


@pytest.mark.asyncio
async def test_cv_pipeline_run(
    cv_pipeline: CVPipeline, kg_repository: KGRepository, graph_rag: GraphRAG
) -> None:
    # Arrange
    user_id = "u1"
    job_offer_id = "j1"

    mock_response = AIMessage(
        content=(
            '{"headline": "Expert Developer", "summary": "Expert dev", '
            '"skill_categories": {"Languages": ["Python"]}, "experience": [], '
            '"projects": []}'
        )
    )

    with (
        patch.object(
            kg_repository, "get_node", new_callable=AsyncMock
        ) as mock_get_node,
        patch.object(kg_repository, "query", new_callable=AsyncMock) as mock_query,
        patch.object(
            kg_repository, "find_related_nodes", new_callable=AsyncMock
        ) as mock_find_related,
        patch.object(
            kg_repository, "get_person_skills", new_callable=AsyncMock
        ) as mock_person_skills,
        patch.object(graph_rag, "retrieve", new_callable=AsyncMock) as mock_retrieve,
        patch("langchain_deepseek.ChatDeepSeek.ainvoke", return_value=mock_response),
    ):
        # fetch_job_offer: JobOffer node, then fetch_static_profile: Person node.
        mock_get_node.side_effect = [
            {"id": "j1", "title": "Software Engineer", "description": "Build things"},
            {"id": "u1", "name": "John Doe"},
        ]
        # fetch_job_offer: REQUIRES query, then fetch_static_profile: certificates query.
        mock_query.side_effect = [
            [],
            [
                {
                    "cert": {"id": "c1", "title": "AWS SAA", "issuer": "AWS"},
                    "validated_skills": [],
                }
            ],
        ]
        # fetch_static_profile fetches employment, education, projects (in that order).
        mock_find_related.side_effect = [
            [{"title": "Engineer", "company": "Acme", "start_date": "2020-01-01"}],
            [{"institution": "MIT", "degree": "BSc", "start_date": "2016-01-01"}],
            [_project("p1", "Side Project", ["Python"])],
        ]
        mock_person_skills.return_value = [
            {"id": "skill_python", "name": "Python", "category": "language"}
        ]
        mock_retrieve.return_value = []

        # Act
        result = await cv_pipeline.run(user_id, job_offer_id)

        # Assert
        assert result["generated"]["summary"] == "Expert dev"
        assert result["generated"]["headline"] == "Expert Developer"
        assert result["profile"] == {"id": "u1", "name": "John Doe"}
        assert result["education"] == [
            {"institution": "MIT", "degree": "BSc", "start_date": "2016-01-01"}
        ]
        # Certificates/projects are the BUDGET-SELECTED subset, not the raw fetch.
        assert result["certificates"] == []  # no VALIDATES overlap, not a retrieval hit
        assert result["projects"] == [_project("p1", "Side Project", ["Python"])]
        mock_get_node.assert_called()
        mock_retrieve.assert_called_once()
        assert mock_retrieve.call_args.kwargs["person_id"] == user_id
        assert mock_retrieve.call_args.kwargs["label_preset"] == "cv"
        assert set(mock_retrieve.call_args.kwargs["labels"]) == {
            "Project",
            "Skill",
            "Certificate",
        }


@pytest.mark.asyncio
async def test_cv_pipeline_budgets_projects_and_skills_despite_large_portfolio(
    cv_pipeline: CVPipeline, kg_repository: KGRepository, graph_rag: GraphRAG
) -> None:
    """Regression test for the GraphRAG-as-curator behavior: even when the
    person has many projects/skills, only a small, job-relevant subset is
    ever passed into the LLM prompt.
    """
    user_id = "u1"
    job_offer_id = "j1"

    all_projects = [_project(f"p{i}", f"Project {i}", ["Python"]) for i in range(10)]

    mock_response = AIMessage(
        content=(
            '{"headline": "Expert Developer", "summary": "Expert dev", '
            '"skill_categories": {}, "experience": [], "projects": []}'
        )
    )

    captured_prompt_text: list[str] = []

    async def _fake_ainvoke(self, *args, **kwargs):  # noqa: ANN001, ARG001
        prompt_value = args[0] if args else None
        captured_prompt_text.append(
            prompt_value.to_string()
            if hasattr(prompt_value, "to_string")
            else str(prompt_value)
        )
        return mock_response

    with (
        patch.object(
            kg_repository, "get_node", new_callable=AsyncMock
        ) as mock_get_node,
        patch.object(kg_repository, "query", new_callable=AsyncMock) as mock_query,
        patch.object(
            kg_repository, "find_related_nodes", new_callable=AsyncMock
        ) as mock_find_related,
        patch.object(
            kg_repository, "get_person_skills", new_callable=AsyncMock
        ) as mock_person_skills,
        patch.object(graph_rag, "retrieve", new_callable=AsyncMock) as mock_retrieve,
        patch("langchain_deepseek.ChatDeepSeek.ainvoke", _fake_ainvoke),
    ):
        mock_get_node.side_effect = [
            {
                "id": "j1",
                "title": "Backend Engineer",
                "description": "Build APIs with Python",
            },
            {"id": "u1", "name": "John Doe"},
        ]
        mock_query.side_effect = [[], []]
        mock_find_related.side_effect = [[], [], all_projects]
        mock_person_skills.return_value = [
            {"id": "skill_python", "name": "Python", "category": "language"}
        ]
        # Only 3 of the 10 projects are ranked as relevant hits.
        mock_retrieve.return_value = [
            {
                "label": "Project",
                "node": {"id": "p0"},
                "weighted_score": 0.9,
                "related": [],
            },
            {
                "label": "Project",
                "node": {"id": "p1"},
                "weighted_score": 0.8,
                "related": [],
            },
            {
                "label": "Project",
                "node": {"id": "p2"},
                "weighted_score": 0.7,
                "related": [],
            },
        ]

        result = await cv_pipeline.run(user_id, job_offer_id)

    assert len(result["projects"]) == 3
    assert {p["id"] for p in result["projects"]} == {"p0", "p1", "p2"}
    assert captured_prompt_text, "LLM should have been invoked"
    prompt_text = captured_prompt_text[0]
    assert "Project 0" in prompt_text
    assert "Project 3" not in prompt_text
