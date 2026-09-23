from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import status
from httpx import AsyncClient

from app.kg.repository import KGRepository
from app.main import app


@pytest.mark.anyio
async def test_get_kg_stats_success(async_client: AsyncClient) -> None:
    # Mock KG repository
    mock_repo = AsyncMock(spec=KGRepository)

    # Mock find_related_nodes for projects and applications
    mock_repo.find_related_nodes.side_effect = [
        [{"id": "p1"}],  # projects
        [{"id": "a1"}],  # applications
    ]
    # Skills tracked uses get_person_skills (same as Skills tab)
    mock_repo.get_person_skills.return_value = [{"id": "s1"}, {"id": "s2"}]

    # Mock query for job matches
    mock_repo.query.return_value = [{"count": 5}]

    # Use dependency override
    app.dependency_overrides[KGRepository] = lambda: mock_repo

    try:
        response = await async_client.get("/api/v1/kg/stats")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["active_projects"] == 1
        assert data["skills_tracked"] == 2
        assert data["open_applications"] == 1
        assert data["job_matches"] == 5
    finally:
        del app.dependency_overrides[KGRepository]


@pytest.mark.anyio
async def test_get_kg_graph_success(async_client: AsyncClient) -> None:
    mock_repo = AsyncMock(spec=KGRepository)

    mock_repo.get_node.return_value = {"id": "user_1", "name": "Test User"}
    mock_repo.get_person_skills.return_value = [{"id": "skill_1", "name": "Python"}]
    mock_repo.query.return_value = [
        {
            "rel_type": "HAS_SKILL",
            "source_id": "user_1",
            "target_id": "skill_1",
            "source_node": {"id": "user_1", "name": "Test User"},
            "source_label": "Person",
            "target_node": {"id": "skill_1", "name": "Python"},
            "target_label": "Skill",
        },
        {
            "rel_type": "USES",
            "source_id": "project_1",
            "target_id": "skill_1",
            "source_node": {"id": "project_1", "title": "Portfolio App"},
            "source_label": "Project",
            "target_node": {"id": "skill_1", "name": "Python"},
            "target_label": "Skill",
        },
    ]

    app.dependency_overrides[KGRepository] = lambda: mock_repo

    try:
        response = await async_client.get("/api/v1/kg/graph")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 3
        assert len(data["edges"]) == 2
        assert {node["id"] for node in data["nodes"]} == {
            "user_1",
            "skill_1",
            "project_1",
        }
        assert data["edges"][0]["label"] == "HAS_SKILL"
        assert data["edges"][0]["source"] == "user_1"
        assert data["edges"][0]["target"] == "skill_1"
        assert data["edges"][0]["properties"] == {}
        assert "animated" not in data["edges"][0]
        assert data["edges"][1]["label"] == "USES"
        assert data["edges"][1]["source"] == "project_1"
        assert data["edges"][1]["target"] == "skill_1"
        assert data["person_name"] == "Test User"
        assert data["person_id"] == "user_1"
        skill = next(node for node in data["nodes"] if node["id"] == "skill_1")
        assert skill["data"]["properties"]["has_direct_link"] is True
        assert skill["data"]["properties"]["evidence_count"] == 1
        assert skill["data"]["properties"]["demand_count"] == 0
    finally:
        del app.dependency_overrides[KGRepository]


@pytest.mark.anyio
async def test_get_kg_graph_empty_when_person_missing(
    async_client: AsyncClient,
) -> None:
    mock_repo = AsyncMock(spec=KGRepository)
    mock_repo.get_node.return_value = None

    app.dependency_overrides[KGRepository] = lambda: mock_repo

    try:
        response = await async_client.get("/api/v1/kg/graph")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"nodes": [], "edges": []}
    finally:
        del app.dependency_overrides[KGRepository]
