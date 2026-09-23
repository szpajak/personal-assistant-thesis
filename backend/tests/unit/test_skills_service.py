from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.skills import SkillCreate
from app.services.skills_service import SkillsService
from app.utils.skill_ids import canonical_skill_id


@pytest.mark.asyncio
async def test_create_skill_uses_canonical_id() -> None:
    repo = MagicMock()
    repo.get_node = AsyncMock(return_value=None)
    repo.upsert_node = AsyncMock()
    repo.upsert_relationship = AsyncMock()
    pipeline = MagicMock()

    service = SkillsService(
        kg_repository=repo,
        skill_analysis_pipeline=pipeline,
    )

    payload = SkillCreate(name="Python", category="technical", level="advanced")
    created = await service.create_skill(person_id="user_1", payload=payload)

    expected_id = canonical_skill_id("Python")
    assert created.id == expected_id
    repo.upsert_node.assert_called_once_with(
        "Skill",
        {
            "id": expected_id,
            "name": "Python",
            "category": "technical",
            "level": "advanced",
            "aliases": [],
        },
    )
