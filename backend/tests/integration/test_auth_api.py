from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.main import app
from app.models.user import User


@pytest.mark.anyio
async def test_register_user_success(async_client: AsyncClient) -> None:
    # Mock DB session
    mock_db = AsyncMock(spec=AsyncSession)

    # Mock result for user existence check (user does not exist)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    # Mock refresh to set ID
    async def mock_refresh(obj: Any) -> None:
        obj.id = 1

    mock_db.refresh.side_effect = mock_refresh

    # Override get_db_session
    app.dependency_overrides[get_db_session] = lambda: mock_db

    payload = {
        "email": "newuser@example.com",
        "password": "password123",
        "full_name": "New User",
    }

    response = await async_client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == payload["email"]
    assert data["full_name"] == payload["full_name"]
    assert "id" in data

    # Verify DB calls
    assert mock_db.add.called
    assert mock_db.commit.called

    # Clean up
    del app.dependency_overrides[get_db_session]


@pytest.mark.anyio
async def test_register_user_already_exists(async_client: AsyncClient) -> None:
    mock_db = AsyncMock(spec=AsyncSession)

    # Mock result for user existence check (user exists)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = User(
        id=1, email="existing@example.com"
    )
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[get_db_session] = lambda: mock_db

    payload = {
        "email": "existing@example.com",
        "password": "password123",
        "full_name": "Existing User",
    }

    response = await async_client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "User with this email already exists"

    del app.dependency_overrides[get_db_session]


@pytest.mark.anyio
async def test_login_success(async_client: AsyncClient) -> None:
    from app.core.security import hash_password

    mock_db = AsyncMock(spec=AsyncSession)

    # Mock user in DB
    user = User(
        id=1,
        email="test@example.com",
        hashed_password=hash_password("correctpassword"),
        full_name="Test User",
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[get_db_session] = lambda: mock_db

    payload = {"email": "test@example.com", "password": "correctpassword"}

    response = await async_client.post("/api/v1/auth/login", json=payload)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    del app.dependency_overrides[get_db_session]


@pytest.mark.anyio
async def test_login_invalid_credentials(async_client: AsyncClient) -> None:
    mock_db = AsyncMock(spec=AsyncSession)

    # Mock user NOT in DB or wrong password
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[get_db_session] = lambda: mock_db

    payload = {"email": "wrong@example.com", "password": "wrongpassword"}

    response = await async_client.post("/api/v1/auth/login", json=payload)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid email or password"

    del app.dependency_overrides[get_db_session]
