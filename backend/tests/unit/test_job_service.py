from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.job_service import JobService


def _staging_listing(**overrides: object) -> SimpleNamespace:
    data: dict[str, object] = {
        "id": "listing-1",
        "title": "Backend Engineer",
        "company": "Acme",
        "description": "Python and Docker required. Kubernetes is a plus.",
        "required_skills": [],
        "url": "https://example.com/1",
        "location": "Remote",
        "salary_range": None,
        "source": "indeed",
        "external_id": "1",
        "scraped_at": datetime.now(UTC),
        "posted_at": None,
        "status": "active",
        "job_type": None,
        "search_term": "python",
        "seniority": "mid",
        "min_experience_years": None,
        "max_experience_years": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.mark.asyncio
async def test_list_cached_matches_includes_staging_heuristic_overlap() -> None:
    kg = MagicMock()
    kg.get_person_skills = AsyncMock(return_value=[{"name": "Python"}])
    kg.query = AsyncMock(return_value=[])
    kg.list_skill_names = AsyncMock(return_value=["Python", "Docker"])

    listing_repo = MagicMock()
    listing_repo.list_listings = AsyncMock(return_value=[_staging_listing()])
    match_repo = MagicMock()
    match_repo.list_for_person = AsyncMock(return_value=[])

    with patch(
        "app.services.job_service.compute_skill_fingerprint",
        new=AsyncMock(return_value="fp"),
    ):
        service = JobService(
            kg_repository=kg,
            job_match_pipeline=MagicMock(),
            job_listing_repository=listing_repo,
            job_match_repository=match_repo,
            kg_ingestion=MagicMock(),
        )
        matches = await service.list_cached_matches("user_1")

    assert len(matches) == 1
    assert matches[0].job_offer.tier == "staging"
    assert "Python" in matches[0].job_offer.required_skills
    assert "Docker" in matches[0].job_offer.required_skills
    assert matches[0].quick_score > 0
    assert "Python" in matches[0].matching_skills
    assert matches[0].source == "none"


@pytest.mark.asyncio
async def test_list_scraped_seeds_skills_when_listing_has_none() -> None:
    kg = MagicMock()
    kg.list_skill_names = AsyncMock(return_value=["Python"])
    listing_repo = MagicMock()
    listing_repo.list_listings = AsyncMock(return_value=[_staging_listing()])

    service = JobService(
        kg_repository=kg,
        job_match_pipeline=MagicMock(),
        job_listing_repository=listing_repo,
        job_match_repository=MagicMock(),
        kg_ingestion=MagicMock(),
    )
    offers = await service.list_scraped()

    assert len(offers) == 1
    assert "Python" in offers[0].required_skills
    assert "Docker" in offers[0].required_skills
