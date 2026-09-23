from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..config import settings

# Process-wide engine for the FastAPI app (one long-lived asyncio event loop).
# Celery tasks MUST NOT reuse this — each ``asyncio.run()`` creates a new loop,
# and asyncpg connections bound to a previous loop raise
# "Future attached to a different loop" / "another operation is in progress".
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,
)
async_session_factory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


def get_async_session() -> AsyncSession:
    return async_session_factory()


@asynccontextmanager
async def celery_db_session() -> AsyncIterator[AsyncSession]:
    """Fresh engine + session scoped to one Celery ``asyncio.run()`` call.

    Creates and disposes the engine inside the current event loop so asyncpg
    never sees cross-loop connection reuse.
    """
    task_engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_size=1,
        max_overflow=0,
    )
    session_factory = async_sessionmaker(
        bind=task_engine,
        expire_on_commit=False,
    )
    session = session_factory()
    try:
        yield session
    finally:
        await session.close()
        await task_engine.dispose()
