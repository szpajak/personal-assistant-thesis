from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings
from app.tasks.email_tasks import resolve_primary_person_id


@pytest.mark.anyio
async def test_resolve_primary_person_id_from_seed_user() -> None:
    user = MagicMock()
    user.id = 3
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    session.execute.return_value = result

    @asynccontextmanager
    async def fake_celery_db_session():
        yield session

    with patch("app.tasks.email_tasks.celery_db_session", fake_celery_db_session):
        person_id = await resolve_primary_person_id()

    assert person_id == "user_3"


@pytest.mark.anyio
async def test_resolve_primary_person_id_falls_back_on_error() -> None:
    @asynccontextmanager
    async def fake_celery_db_session():
        raise RuntimeError("another operation is in progress")
        yield  # pragma: no cover

    with patch("app.tasks.email_tasks.celery_db_session", fake_celery_db_session):
        person_id = await resolve_primary_person_id()

    assert person_id == settings.primary_person_id
