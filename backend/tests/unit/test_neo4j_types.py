from __future__ import annotations

from datetime import timezone

from neo4j.time import DateTime

from app.utils.neo4j_types import neo4j_to_python


def test_neo4j_datetime_becomes_isoformat_string() -> None:
    value = DateTime(2026, 4, 15, 12, 0, 0, 749000000, timezone.utc)
    converted = neo4j_to_python({"applied_at": value})
    assert isinstance(converted["applied_at"], str)
    assert converted["applied_at"].startswith("2026-04-15T12:00:00")
