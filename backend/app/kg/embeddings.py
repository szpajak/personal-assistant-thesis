from __future__ import annotations

import logging
import os
import threading
from typing import TYPE_CHECKING, cast

from sentence_transformers import SentenceTransformer

from ..config import settings

if TYPE_CHECKING:
    from .repository import KGRepository

logger = logging.getLogger(__name__)

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

_model_cache: SentenceTransformer | None = None
_model_cache_name: str | None = None
_model_lock = threading.Lock()


def _load_sentence_transformer(model_name: str) -> SentenceTransformer:
    """Load SentenceTransformer on CPU without triggering meta-tensor moves.

    Passing ``device="cpu"`` to the constructor can call ``.to("cpu")`` on
    weights that were lazily placed on the ``meta`` device, which raises
    "Cannot copy out of meta tensor". Loading without an explicit device and
    disabling ``low_cpu_mem_usage`` avoids that path.
    """
    load_attempts: list[dict[str, object]] = [
        {"model_kwargs": {"low_cpu_mem_usage": False}},
        {"model_kwargs": {"low_cpu_mem_usage": False}, "local_files_only": True},
        {},
    ]

    last_error: Exception | None = None
    for kwargs in load_attempts:
        try:
            model = SentenceTransformer(model_name, **kwargs)
            logger.info(
                "Loaded SentenceTransformer model %s (kwargs=%s)",
                model_name,
                kwargs,
            )
            return model
        except Exception as e:  # noqa: BLE001 - retry with alternate kwargs
            last_error = e
            logger.warning(
                "SentenceTransformer load attempt failed (kwargs=%s): %s",
                kwargs,
                e,
            )

    raise RuntimeError(
        f"Failed to load SentenceTransformer model {model_name}"
    ) from last_error


def get_embedding_model(model_name: str) -> SentenceTransformer | None:
    """Return a process-wide cached SentenceTransformer instance."""
    global _model_cache, _model_cache_name

    if _model_cache is not None and _model_cache_name == model_name:
        return _model_cache

    with _model_lock:
        if _model_cache is not None and _model_cache_name == model_name:
            return _model_cache
        try:
            _model_cache = _load_sentence_transformer(model_name)
            _model_cache_name = model_name
            return _model_cache
        except Exception as e:
            logger.error("Failed to initialize SentenceTransformer: %s", e)
            return None


class KGEmbeddings:
    """Service for generating and managing Knowledge Graph embeddings using Hugging Face."""

    def __init__(self, kg_repository: KGRepository | None = None) -> None:
        """Initialize embeddings service.

        Args:
            kg_repository: Optional repository for direct graph updates

        """
        self.model_name = settings.huggingface_embedding_model
        self._model = get_embedding_model(self.model_name)

        if kg_repository is None:
            from .repository import KGRepository

            self.kg_repository = KGRepository()
        else:
            self.kg_repository = kg_repository

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding vector for text using Hugging Face.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats

        """
        if self._model is None:
            logger.warning("Embeddings model not initialized, returning zero vector")
            return [0.0] * settings.huggingface_embedding_dimension

        try:
            embedding = self._model.encode(text, normalize_embeddings=True)
            return cast(list[float], embedding.tolist())
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return [0.0] * settings.huggingface_embedding_dimension

    async def index_node_embedding(
        self,
        node_id: str,
        label: str,
        vector: list[float],
    ) -> None:
        """Store embedding vector for a node in Neo4j.

        Args:
            node_id: Node identifier
            label: Node label
            vector: Embedding vector

        """
        await self.kg_repository.upsert_node(
            label, {"id": node_id, "embedding": vector}
        )
        logger.info(f"Indexed embedding for {label} node {node_id}")

    async def embed_and_store(
        self,
        node_id: str,
        label: str,
        text: str,
    ) -> list[float]:
        """Generate embedding for text and store it.

        Args:
            node_id: Node identifier
            label: Node label
            text: Text to embed

        Returns:
            Generated embedding vector

        """
        vector = await self.embed_text(text)
        await self.index_node_embedding(node_id, label, vector)
        return vector
