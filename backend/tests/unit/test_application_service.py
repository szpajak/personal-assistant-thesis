from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.schemas.applications import ApplicationCreate, ApplicationUpdate
from app.services.application_service import ApplicationService


def _job_props() -> dict:
    return {
        "id": "job_1",
        "title": "Engineer",
        "company": "Tech",
        "url": "http://example.com",
        "description": "Desc",
        "required_skills": ["Python"],
        "scraped_at": datetime.now(),
    }


@pytest.mark.anyio
async def test_create_application() -> None:
    mock_repo = AsyncMock()
    mock_ingestion = AsyncMock()
    mock_ingestion.promote_job.return_value = (_job_props(), True)
    service = ApplicationService(
        kg_repository=mock_repo,
        kg_ingestion=mock_ingestion,
        job_listing_repository=AsyncMock(),
    )

    payload = ApplicationCreate(
        job_offer_id="job_1",
        status="applied",
        applied_at=datetime(2024, 5, 1, 0, 0),
        notes="Applied via LinkedIn",
    )

    result = await service.create_application("user_1", payload)

    assert result.status == "Applied"
    assert result.notes == "Applied via LinkedIn"
    assert result.job_offer is not None
    assert result.job_offer.id == "job_1"
    assert result.job_offer.tier == "career"
    mock_ingestion.promote_job.assert_awaited_once()
    assert mock_repo.upsert_node.called
    assert mock_repo.upsert_relationship.called


@pytest.mark.anyio
async def test_list_applications() -> None:
    mock_repo = AsyncMock()
    mock_repo.query.return_value = [
        {
            "app": {
                "id": "app_1",
                "status": "interviewing",
                "applied_at": "2024-04-15",
            },
            "job": _job_props(),
        }
    ]
    # Explicit mock so the service doesn't construct a real KGIngestion
    # (which would load an actual SentenceTransformer model).
    service = ApplicationService(
        kg_repository=mock_repo,
        kg_ingestion=AsyncMock(),
        job_listing_repository=AsyncMock(),
    )

    result = await service.list_applications("user_1")

    assert len(result) == 1
    assert result[0].id == "app_1"
    assert result[0].status == "Interview"
    assert result[0].job_offer is not None
    assert result[0].job_offer.title == "Engineer"


@pytest.mark.anyio
async def test_update_application() -> None:
    mock_repo = AsyncMock()
    mock_repo.get_node.return_value = {"id": "app_1", "status": "interviewing"}
    mock_repo.query.return_value = [
        {
            "app": {
                "id": "app_1",
                "status": "offer",
                "applied_at": "2024-04-15",
                "notes": None,
            },
            "job": _job_props(),
        }
    ]

    service = ApplicationService(
        kg_repository=mock_repo,
        kg_ingestion=AsyncMock(),
        job_listing_repository=AsyncMock(),
    )

    payload = ApplicationUpdate(status="offer")
    result = await service.update_application("app_1", payload)

    assert result is not None
    assert result.status == "Offer"
    assert result.job_offer is not None
    assert result.job_offer.id == "job_1"
    assert mock_repo.upsert_node.called


@pytest.mark.anyio
async def test_list_applications_coerces_neo4j_datetime() -> None:
    from datetime import timezone

    from neo4j.time import DateTime

    mock_repo = AsyncMock()
    mock_repo.query.return_value = [
        {
            "app": {
                "id": "app_1",
                "status": "Applied",
                "applied_at": DateTime(2026, 4, 15, 12, 0, 0, 749000000, timezone.utc),
            },
            "job": _job_props(),
        }
    ]
    service = ApplicationService(
        kg_repository=mock_repo,
        kg_ingestion=AsyncMock(),
        job_listing_repository=AsyncMock(),
    )

    result = await service.list_applications("user_1")

    assert len(result) == 1
    assert result[0].applied_at is not None
    assert result[0].applied_at.year == 2026
    assert result[0].applied_at.month == 4
    assert result[0].applied_at.day == 15


@pytest.mark.anyio
async def test_list_applications_skips_malformed_row() -> None:
    mock_repo = AsyncMock()
    mock_repo.query.return_value = [
        {
            "app": {"id": "bad", "status": "Applied", "applied_at": object()},
            "job": None,
        },
        {
            "app": {
                "id": "app_ok",
                "status": "Applied",
                "applied_at": "2024-04-15",
            },
            "job": _job_props(),
        },
    ]
    service = ApplicationService(
        kg_repository=mock_repo,
        kg_ingestion=AsyncMock(),
        job_listing_repository=AsyncMock(),
    )

    result = await service.list_applications("user_1")

    assert len(result) == 1
    assert result[0].id == "app_ok"


@pytest.mark.anyio
async def test_list_application_emails_coerces_received_at() -> None:
    from datetime import timezone

    from neo4j.time import DateTime

    mock_repo = AsyncMock()
    mock_repo.query.side_effect = [
        [{"id": "app_1"}],
        [
            {
                "email": {
                    "id": "e1",
                    "subject": "Hi",
                    "sender": "hr@acme.com",
                    "received_at": DateTime(2026, 4, 15, 12, 0, 0, 0, timezone.utc),
                    "summary": "Hello",
                    "classification": "career_related",
                }
            }
        ],
    ]
    service = ApplicationService(
        kg_repository=mock_repo,
        kg_ingestion=AsyncMock(),
        job_listing_repository=AsyncMock(),
    )

    emails = await service.list_application_emails("user_1", "app_1")

    assert emails is not None
    assert len(emails) == 1
    assert emails[0].received_at is not None
    assert emails[0].classification == "career_related"
