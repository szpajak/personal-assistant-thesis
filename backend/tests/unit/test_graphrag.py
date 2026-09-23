from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.kg.graphrag import GraphRAG
from app.kg.repository import KGRepository


@pytest.mark.asyncio
async def test_assemble_context(
    graph_rag: GraphRAG, kg_repository: KGRepository, mock_embeddings: MagicMock
) -> None:
    # Arrange
    query = "python developer"

    with (
        patch.object(
            mock_embeddings, "embed_text", new_callable=AsyncMock
        ) as mock_embed,
        patch.object(
            kg_repository, "count_nodes", new_callable=AsyncMock
        ) as mock_count_nodes,
        patch.object(
            kg_repository, "vector_search", new_callable=AsyncMock
        ) as mock_vector_search,
        patch.object(
            kg_repository, "fulltext_search", new_callable=AsyncMock
        ) as mock_fulltext_search,
        patch.object(
            kg_repository, "find_related_nodes_typed", new_callable=AsyncMock
        ) as mock_find_related,
    ):
        mock_embed.return_value = [0.1, 0.2, 0.3]
        mock_count_nodes.return_value = 1  # gate Certificate search open
        mock_vector_search.return_value = [
            {
                "node": {"id": "1", "title": "Python Project"},
                "score": 0.9,
                "label": "Project",
            }
        ]
        mock_fulltext_search.return_value = []
        mock_find_related.return_value = [
            {
                "node": {"name": "Python", "id": "skill_python"},
                "relationship_type": "USES",
                "relationship_props": {},
            }
        ]

        # Act
        context = await graph_rag.assemble_context(query)

        # Assert
        assert "Query: python developer" in context
        assert "Python Project" in context
        assert "Python" in context
        mock_embed.assert_called_once_with(query)
        # 4 labels searched: Project, Skill, JobOffer, Certificate (gated open above)
        assert mock_vector_search.call_count == 4
        assert mock_fulltext_search.call_count == 4


@pytest.mark.asyncio
async def test_retrieve_relevant_skills(graph_rag: GraphRAG) -> None:
    # Arrange
    job_title = "Backend Engineer"
    mock_response = MagicMock()
    mock_response.content = '[{"name": "Python"}, {"name": "FastAPI"}]'

    with patch("app.kg.graphrag.create_skill_extraction_chain") as mock_chain_factory:
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = mock_response
        mock_chain_factory.return_value = mock_chain

        # Act
        skills = await graph_rag.retrieve_relevant_skills(job_title)

        # Assert
        assert "Python" in skills
        assert "FastAPI" in skills
        mock_chain.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_retrieve_related_projects(
    graph_rag: GraphRAG, kg_repository: KGRepository
) -> None:
    # Arrange
    skill_id = "skill_python"
    with patch.object(
        kg_repository, "find_related_nodes", new_callable=AsyncMock
    ) as mock_find:
        mock_find.return_value = [{"id": "p1", "title": "Project 1"}]

        # Act
        projects = await graph_rag.retrieve_related_projects(skill_id)

        # Assert
        assert len(projects) == 1
        assert projects[0]["title"] == "Project 1"
        mock_find.assert_called_once_with(
            start_label="Skill", start_id=skill_id, relationship_type="USES", hops=1
        )


@pytest.mark.asyncio
async def test_match_candidate_to_job(graph_rag: GraphRAG) -> None:
    # Arrange
    candidate_skills = ["Python", "FastAPI"]
    job_description = "We need a Python developer familiar with FastAPI."
    mock_response = MagicMock()
    mock_response.content = (
        '{"match_score": 85, "matching_skills": ["Python", "FastAPI"]}'
    )

    with patch("app.kg.graphrag.create_job_matching_chain") as mock_chain_factory:
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = mock_response
        mock_chain_factory.return_value = mock_chain

        # Act
        match_data = await graph_rag.match_candidate_to_job(
            candidate_skills, job_description
        )

        # Assert
        assert match_data["match_score"] == 85
        assert "Python" in match_data["matching_skills"]
        mock_chain.ainvoke.assert_called_once()
