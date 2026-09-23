"""Convert Neo4j driver values into JSON- and Pydantic-friendly Python types."""

from __future__ import annotations

from datetime import date
from typing import Any


def neo4j_to_python(data: Any) -> Any:
    """Convert Neo4j types to standard Python types for serialization.

    ``properties(n)`` returns ``neo4j.time.DateTime`` for temporal fields.
    Pydantic v2 will not coerce those into ``datetime``, so API handlers that
    build response models from raw node properties must run this first.
    """
    from neo4j.time import Date, DateTime

    if isinstance(data, dict):
        return {k: neo4j_to_python(v) for k, v in data.items()}
    if isinstance(data, list):
        return [neo4j_to_python(v) for v in data]
    if isinstance(data, Date):
        return date(data.year, data.month, data.day).isoformat()
    if isinstance(data, DateTime):
        native = data.to_native()
        return native.isoformat()
    return data
