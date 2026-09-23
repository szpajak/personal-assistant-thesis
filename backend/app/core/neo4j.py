from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from neo4j import AsyncDriver, AsyncGraphDatabase

from ..config import settings

_driver: AsyncDriver | None = None
_driver_loop: asyncio.AbstractEventLoop | None = None


def get_neo4j_driver() -> AsyncDriver:
    """Get or create the Neo4j driver singleton, re-creating it if the
    current event loop has changed since it was built.

    The async Neo4j driver's connection pool is bound to whichever event
    loop was running at creation time. FastAPI runs a single long-lived
    loop, so that's a non-issue there, but every Celery task in this
    codebase wraps its work in a fresh ``asyncio.run(...)`` call (see
    ``app/tasks/*.py``), which spins up a brand-new loop per task and closes
    it afterwards. Naively caching one driver across tasks meant every call
    after the first task in a given worker process failed with "Future
    attached to a different loop" once the original loop was gone. Detect
    that mismatch here and transparently swap in a fresh driver instead -
    the stale one can't be awaited-closed (its loop is already dead) so it's
    just dropped; that's an acceptable trade-off for a Celery worker that
    only does this on its first Neo4j call per task, not a leak that grows
    per-query.
    """
    global _driver, _driver_loop
    try:
        current_loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _driver is not None and _driver_loop is not current_loop:
        _driver = None

    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        _driver_loop = current_loop
    return _driver


async def close_neo4j_driver() -> None:
    """Close the Neo4j driver and reset the singleton."""
    global _driver, _driver_loop
    if _driver is not None:
        await _driver.close()
        _driver = None
        _driver_loop = None


@asynccontextmanager
async def get_neo4j_session() -> AsyncGenerator[Any, None]:
    """Context manager for Neo4j async session."""
    driver = get_neo4j_driver()
    session = driver.session()
    try:
        yield session
    finally:
        await session.close()
