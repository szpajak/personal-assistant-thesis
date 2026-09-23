from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_skills(async_client: AsyncClient) -> None:
    # Arrange
    with (
        patch(
            "app.kg.repository.KGRepository.get_person_skills", new_callable=AsyncMock
        ) as mock_find,
        patch(
            "app.kg.repository.KGRepository.ensure_has_skill_for_finished_projects",
            new_callable=AsyncMock,
            return_value=0,
        ),
    ):
        mock_find.return_value = [
            {"id": "s1", "name": "Python", "category": "technical", "level": "expert"}
        ]

        # Act
        response = await async_client.get("/api/v1/skills/?person_id=u1")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Python"


@pytest.mark.asyncio
async def test_skill_analysis(async_client: AsyncClient) -> None:
    # Arrange
    with patch(
        "app.services.skills_service.SkillAnalysisPipeline.run", new_callable=AsyncMock
    ) as mock_run:
        mock_run.return_value = {
            "core_strengths": ["Python"],
            "skill_gaps": [
                {"skill": "AWS", "gap_reason": "In demand", "priority": "high"}
            ],
            "target_role_ready": True,
            "target_role_title": None,
            "sample_status": None,
            "sample_job_count": 0,
        }

        # Act
        response = await async_client.get("/api/v1/skills/analysis?person_id=u1")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "Python" in data["core_strengths"]
        assert any(gap["skill"] == "AWS" for gap in data["skill_gaps"])
