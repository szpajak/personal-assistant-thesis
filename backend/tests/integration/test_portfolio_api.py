from __future__ import annotations

import io
from datetime import date
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from httpx import AsyncClient

from app.api.v1.portfolio import get_portfolio_service
from app.main import app
from app.schemas.portfolio import ProjectDraft, SkillDraft


@pytest.mark.anyio
async def test_list_portfolio_success(async_client: AsyncClient) -> None:
    # Mock Portfolio service
    mock_service = AsyncMock()
    mock_service.list_projects.return_value = [
        {
            "id": "proj_1",
            "title": "Project 1",
            "description": "Desc 1",
            "tech_stack": ["Python"],
            "start_date": date(2023, 1, 1),
            "media_urls": [],
        },
        {
            "id": "proj_2",
            "title": "Project 2",
            "description": "Desc 2",
            "tech_stack": ["TypeScript"],
            "start_date": date(2023, 6, 1),
            "media_urls": [],
        },
    ]

    # Override get_portfolio_service
    app.dependency_overrides[get_portfolio_service] = lambda: mock_service

    response = await async_client.get("/api/v1/portfolio/")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 2
    assert data[0]["title"] == "Project 1"

    # Clean up
    del app.dependency_overrides[get_portfolio_service]


@pytest.mark.anyio
async def test_create_project_success(async_client: AsyncClient) -> None:
    mock_service = AsyncMock()
    mock_service.create_project.return_value = {
        "id": "proj_new",
        "title": "New Project",
        "description": "New Desc",
        "tech_stack": ["React"],
        "start_date": date(2024, 1, 1),
        "media_urls": [],
        "seniority": "mid",
        "achievements": [],
        "skills": [],
        "skip_enrichment": False,
    }

    app.dependency_overrides[get_portfolio_service] = lambda: mock_service

    payload = {
        "title": "New Project",
        "description": "New Desc",
        "tech_stack": ["React"],
        "start_date": "2024-01-01",
    }

    response = await async_client.post("/api/v1/portfolio/", json=payload)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == "proj_new"
    assert data["title"] == "New Project"

    del app.dependency_overrides[get_portfolio_service]


@pytest.mark.anyio
async def test_create_project_with_confirmed_draft_skips_enrichment(
    async_client: AsyncClient,
) -> None:
    mock_service = AsyncMock()
    mock_service.create_project.return_value = {
        "id": "proj_confirmed",
        "title": "Confirmed Project",
        "description": "Reviewed draft",
        "tech_stack": ["Rust"],
        "start_date": date(2024, 1, 1),
        "media_urls": [],
        "seniority": "senior",
        "achievements": ["Shipped to prod"],
        "skills": [
            {
                "name": "Rust",
                "canonical_name": "Rust",
                "category": "language",
                "confidence": 0.9,
            }
        ],
        "skip_enrichment": True,
    }

    app.dependency_overrides[get_portfolio_service] = lambda: mock_service

    payload = {
        "title": "Confirmed Project",
        "description": "Reviewed draft",
        "tech_stack": ["Rust"],
        "start_date": "2024-01-01",
        "seniority": "senior",
        "achievements": ["Shipped to prod"],
        "skills": [
            {
                "name": "Rust",
                "canonical_name": "Rust",
                "category": "language",
                "confidence": 0.9,
            }
        ],
        "skip_enrichment": True,
    }

    response = await async_client.post("/api/v1/portfolio/", json=payload)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == "proj_confirmed"
    assert data["seniority"] == "senior"
    assert data["skip_enrichment"] is True

    del app.dependency_overrides[get_portfolio_service]


@pytest.mark.anyio
async def test_upload_project_document_returns_drafts(
    async_client: AsyncClient,
) -> None:
    mock_service = AsyncMock()
    mock_service.extract_project_drafts.return_value = [
        ProjectDraft(
            title="Uploaded Project",
            description="Extracted Desc",
            skills=[
                SkillDraft(
                    name="AI", canonical_name="AI", category="technical", confidence=0.8
                )
            ],
            tech_stack=["AI"],
            start_date=date(2024, 2, 1),
            source="upload",
        )
    ]

    app.dependency_overrides[get_portfolio_service] = lambda: mock_service

    # Simulate file upload
    files = {
        "file": ("resume.pdf", io.BytesIO(b"dummy pdf content"), "application/pdf")
    }

    response = await async_client.post("/api/v1/portfolio/upload", files=files)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["drafts"]) == 1
    assert data["drafts"][0]["title"] == "Uploaded Project"
    assert data["drafts"][0]["source"] == "upload"

    # Verify extraction call (we don't check the path as it's random) and
    # that nothing was committed to the KG from this endpoint.
    assert mock_service.extract_project_drafts.called
    mock_service.create_project.assert_not_called()

    del app.dependency_overrides[get_portfolio_service]


@pytest.mark.anyio
async def test_upload_project_document_multiple_drafts(
    async_client: AsyncClient,
) -> None:
    mock_service = AsyncMock()
    mock_service.extract_project_drafts.return_value = [
        ProjectDraft(title="Project A", description="First", source="upload"),
        ProjectDraft(title="Project B", description="Second", source="upload"),
    ]

    app.dependency_overrides[get_portfolio_service] = lambda: mock_service

    files = {"file": ("cv.pdf", io.BytesIO(b"dummy cv content"), "application/pdf")}

    response = await async_client.post("/api/v1/portfolio/upload", files=files)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert [d["title"] for d in data["drafts"]] == ["Project A", "Project B"]

    del app.dependency_overrides[get_portfolio_service]
