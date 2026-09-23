from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.schemas.profile import EducationRead, EmploymentRead, TargetRoleRead
from app.services.profile_service import ProfileService


@pytest.mark.asyncio
async def test_get_summary_merges_overlapping_employment() -> None:
    service = ProfileService(
        kg_repository=AsyncMock(),
        kg_ingestion=AsyncMock(),
    )
    service.list_employment = AsyncMock(
        return_value=[
            EmploymentRead(
                id="e1",
                title="Dev",
                company="A",
                start_date=date(2020, 1, 1),
                end_date=date(2022, 1, 1),
            ),
            EmploymentRead(
                id="e2",
                title="Senior Dev",
                company="B",
                start_date=date(2021, 6, 1),
                end_date=date(2023, 1, 1),
            ),
        ]
    )
    service.list_education = AsyncMock(
        return_value=[
            EducationRead(
                id="ed1",
                institution="Uni",
                degree="BSc",
                start_date=date(2016, 1, 1),
                end_date=date(2020, 1, 1),
            )
        ]
    )
    service.list_target_roles = AsyncMock(
        return_value=[TargetRoleRead(id="t1", title="Staff Engineer", required_skills=[])]
    )

    summary = await service.get_summary("user_1")
    # Overlap merges to 2020-01-01 .. 2023-01-01 ≈ 3.0 years
    assert summary.total_years_experience == 3.0
    assert summary.employment_count == 2
    assert summary.education_count == 1
    assert summary.target_role_count == 1
