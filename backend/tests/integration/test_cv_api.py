from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import status
from httpx import AsyncClient

from app.api.v1.cv import get_cv_service
from app.main import app


@pytest.mark.anyio
async def test_generate_cv_success(async_client: AsyncClient) -> None:
    # Mock CV service
    mock_service = AsyncMock()
    mock_service.generate_personalized_cv.return_value = {
        "cv_content": "Generated CV Content",
        "cached": False,
    }

    # Override get_cv_service
    app.dependency_overrides[get_cv_service] = lambda: mock_service

    job_id = "job_123"
    response = await async_client.post(f"/api/v1/cv/generate?job_id={job_id}")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["cv_content"] == "Generated CV Content"

    # Verify service call
    mock_service.generate_personalized_cv.assert_called_once()

    # Clean up
    del app.dependency_overrides[get_cv_service]
