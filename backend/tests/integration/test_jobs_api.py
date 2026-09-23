from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_jobs(async_client: AsyncClient) -> None:
    # Arrange
    with patch(
        "app.kg.repository.KGRepository.query", new_callable=AsyncMock
    ) as mock_query:
        mock_query.return_value = [
            {
                "job": {
                    "id": "j1",
                    "title": "Software Engineer",
                    "company": "TechCorp",
                    "url": "http://tech.corp/j1",
                    "description": "Fun job",
                    "required_skills": ["Python"],
                    "scraped_at": "2024-05-09T00:00:00",
                }
            }
        ]

        # Act
        response = await async_client.get("/api/v1/jobs/")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Software Engineer"


@pytest.mark.asyncio
async def test_match_jobs(async_client: AsyncClient) -> None:
    # Arrange
    # Mocking the pipeline run inside the service
    with patch(
        "app.services.job_service.JobMatchPipeline.run", new_callable=AsyncMock
    ) as mock_run:
        mock_run.return_value = [{"job_id": "j1", "match_score": 80}]

        with patch(
            "app.kg.repository.KGRepository.get_node", new_callable=AsyncMock
        ) as mock_get_node:
            mock_get_node.return_value = {
                "id": "j1",
                "title": "Software Engineer",
                "company": "TechCorp",
                "description": "Fun job",
                "scraped_at": "2024-05-09T00:00:00",
            }

            # Act
            response = await async_client.get("/api/v1/jobs/match?person_id=u1")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["score"] == 0.8


@pytest.mark.asyncio
async def test_trigger_job_scrape(async_client: AsyncClient) -> None:
    with patch("app.api.v1.jobs.celery_app.send_task") as mock_send_task:
        mock_send_task.return_value = MagicMock(id="task-123")

        response = await async_client.post(
            "/api/v1/jobs/scrape",
            json={
                "search_term": "Python Developer",
                "location": "Warsaw",
                "country": "Poland",
                "job_type": "fulltime",
                "is_remote": True,
                "hours_old": 72,
                "sites": ["linkedin", "indeed"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task-123"
        mock_send_task.assert_called_once()
        assert (
            mock_send_task.call_args.args[0] == "app.tasks.job_tasks.scrape_job_offers"
        )
        filters = mock_send_task.call_args.kwargs["kwargs"]["filters"]
        assert filters["search_term"] == "Python Developer"
        assert filters["country"] == "Poland"
        assert filters["job_type"] == "fulltime"


@pytest.mark.asyncio
async def test_trigger_job_scrape_requires_search_term(
    async_client: AsyncClient,
) -> None:
    response = await async_client.post("/api/v1/jobs/scrape", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_promote_job(async_client: AsyncClient) -> None:
    from datetime import datetime

    from app.schemas.jobs import JobOfferRead, JobPromoteResponse

    with patch(
        "app.services.job_service.JobService.promote_job", new_callable=AsyncMock
    ) as mock_promote:
        mock_promote.return_value = JobPromoteResponse(
            job_offer=JobOfferRead(
                id="job-1",
                title="Engineer",
                company="Acme",
                url="https://example.com",
                description="Desc",
                required_skills=["Python"],
                scraped_at=datetime.now(),
                tier="career",
            ),
            promoted=True,
        )

        response = await async_client.post("/api/v1/jobs/job-1/promote")

        assert response.status_code == 200
        data = response.json()
        assert data["promoted"] is True
        assert data["job_offer"]["tier"] == "career"
        assert data["job_offer"]["id"] == "job-1"
