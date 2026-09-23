from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.router import api_router
from .core.neo4j import close_neo4j_driver, get_neo4j_driver
from .kg.repository import KGRepository


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """FastAPI lifespan context manager for startup/shutdown events."""
    # Startup: initialize Neo4j driver
    try:
        driver = get_neo4j_driver()
        # Verify connection
        await driver.verify_connectivity()
        await KGRepository().backfill_job_offer_properties()
    except Exception as e:
        raise RuntimeError(f"Failed to connect to Neo4j: {e}") from e

    yield

    # Shutdown: close Neo4j driver
    await close_neo4j_driver()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Career Assistant API",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
