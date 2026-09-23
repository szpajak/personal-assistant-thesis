from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

# Set dummy environment variables for testing before importing app
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:pass@localhost/db"
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USER"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "password"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["OPENAI_API_KEY"] = "sk-test"
os.environ["DEEPSEEK_API_KEY"] = "ds-test"
os.environ["IMAP_HOST"] = "imap.test.com"
os.environ["IMAP_PORT"] = "993"
os.environ["IMAP_USER"] = "test@test.com"
os.environ["IMAP_PASSWORD"] = "password"
os.environ["NEXT_PUBLIC_API_BASE_URL"] = "http://localhost:3000"

import pytest
from httpx import ASGITransport, AsyncClient
from neo4j import AsyncDriver, AsyncSession
from sqlalchemy.ext.asyncio import AsyncSession as SQLAAsyncSession

from app.core.security import create_access_token
from app.kg.graphrag import GraphRAG
from app.kg.repository import KGRepository
from app.models.user import User


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def mock_neo4j_session() -> AsyncMock:
    """Mock for Neo4j AsyncSession."""
    session = AsyncMock(spec=AsyncSession)
    # Support for 'async with driver.session() as session:'
    session.__aenter__.return_value = session
    return session


@pytest.fixture
def mock_neo4j_driver(mock_neo4j_session: AsyncMock) -> MagicMock:
    """Mock for Neo4j AsyncDriver."""
    driver = MagicMock(spec=AsyncDriver)
    driver.session.return_value = mock_neo4j_session
    driver.verify_connectivity = AsyncMock()
    return driver


@pytest.fixture(autouse=True)
def patch_neo4j_driver(
    mock_neo4j_driver: MagicMock,
) -> Generator[MagicMock, None, None]:
    """Patch get_neo4j_driver globally for all tests."""
    with patch("app.kg.repository.get_neo4j_driver", return_value=mock_neo4j_driver):
        with patch("app.core.neo4j.get_neo4j_driver", return_value=mock_neo4j_driver):
            yield mock_neo4j_driver


@pytest.fixture
def kg_repository() -> KGRepository:
    """KGRepository instance."""
    return KGRepository()


@pytest.fixture
def db_session() -> AsyncMock:
    """Placeholder for PostgreSQL async session mock."""
    return AsyncMock(spec=SQLAAsyncSession)


@pytest.fixture
def mock_embeddings() -> MagicMock:
    """Mock for KGEmbeddings service."""
    from app.kg.embeddings import KGEmbeddings

    embeddings = MagicMock(spec=KGEmbeddings)
    embeddings.embed_text = AsyncMock(return_value=[0.1, 0.2, 0.3])
    embeddings.embed_and_store = AsyncMock(return_value=[0.1, 0.2, 0.3])
    return embeddings


@pytest.fixture
def graph_rag(kg_repository: KGRepository, mock_embeddings: MagicMock) -> GraphRAG:
    """GraphRAG instance."""
    from app.kg.graphrag import GraphRAG

    return GraphRAG(kg_repository=kg_repository, embeddings=mock_embeddings)


@pytest.fixture
def mock_openai_client() -> AsyncMock:
    """Mock for OpenAI AsyncOpenAI client."""
    client = AsyncMock()
    client.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.1, 0.2, 0.3])]
    )
    return client


@pytest.fixture
def mock_user() -> User:
    """Mock authenticated user."""
    user = User(id=1, email="test@example.com", full_name="Test User")
    return user


@pytest.fixture
def auth_token(mock_user: User) -> str:
    """Generate valid JWT token for mock user."""
    return create_access_token({"sub": str(mock_user.id)})


@pytest.fixture(autouse=True)
def override_auth(mock_user: User) -> Generator[None, None, None]:
    """Globally override get_current_user dependency for testing."""
    from app.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Async client for FastAPI app testing."""
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
