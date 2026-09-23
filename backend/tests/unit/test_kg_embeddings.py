from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.kg.embeddings import KGEmbeddings


def _mock_model() -> MagicMock:
    """Mock SentenceTransformer that returns a fixed embedding vector."""
    model = MagicMock()
    vector = MagicMock()
    vector.tolist.return_value = [0.1, 0.2, 0.3]
    model.encode.return_value = vector
    return model


@pytest.mark.asyncio
async def test_embed_text() -> None:
    # Arrange
    text = "test text"

    with patch("app.kg.embeddings.get_embedding_model", return_value=_mock_model()):
        embeddings = KGEmbeddings(kg_repository=MagicMock())

        # Act
        vector = await embeddings.embed_text(text)

        # Assert
        assert vector == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_embed_text_falls_back_to_zero_vector_when_model_unavailable() -> None:
    with patch("app.kg.embeddings.get_embedding_model", return_value=None):
        embeddings = KGEmbeddings(kg_repository=MagicMock())

        vector = await embeddings.embed_text("test text")

        # Zero vector sized to the configured embedding dimension.
        from app.config import settings

        assert vector == [0.0] * settings.huggingface_embedding_dimension


@pytest.mark.asyncio
async def test_index_node_embedding() -> None:
    # Arrange
    node_id = "123"
    label = "Project"
    vector = [0.1, 0.2, 0.3]
    mock_repo = MagicMock()
    mock_repo.upsert_node = AsyncMock()

    with patch("app.kg.embeddings.get_embedding_model", return_value=_mock_model()):
        embeddings = KGEmbeddings(kg_repository=mock_repo)

        # Act
        await embeddings.index_node_embedding(node_id, label, vector)

        # Assert
        mock_repo.upsert_node.assert_called_once_with(
            label, {"id": node_id, "embedding": vector}
        )


@pytest.mark.asyncio
async def test_embed_and_store() -> None:
    # Arrange
    node_id = "123"
    label = "Project"
    text = "test text"
    mock_repo = MagicMock()
    mock_repo.upsert_node = AsyncMock()

    with patch("app.kg.embeddings.get_embedding_model", return_value=_mock_model()):
        embeddings = KGEmbeddings(kg_repository=mock_repo)

        # Act
        vector = await embeddings.embed_and_store(node_id, label, text)

        # Assert
        assert vector == [0.1, 0.2, 0.3]
        mock_repo.upsert_node.assert_called_once()
