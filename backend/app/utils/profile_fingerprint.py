"""Deterministic profile fingerprints for cache staleness checks."""

from __future__ import annotations

import hashlib
from typing import Any


def fingerprint_from_skills(skills: list[dict[str, Any]]) -> str:
    """SHA-256 of sorted ``name|level`` pairs (case-normalized)."""
    parts: list[str] = []
    for skill in skills:
        name = str(skill.get("name") or "").strip().lower()
        if not name:
            continue
        level = str(skill.get("level") or "intermediate").strip().lower()
        parts.append(f"{name}|{level}")
    payload = "\n".join(sorted(parts))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fingerprint_from_chronology(
    employment: list[dict[str, Any]],
    education: list[dict[str, Any]],
    certificates: list[dict[str, Any]],
) -> str:
    """Short hash of employment/education/certificate identity for CV cache."""
    lines: list[str] = []
    for row in employment:
        lines.append(
            "emp|"
            f"{row.get('id') or ''}|"
            f"{row.get('start_date') or ''}|"
            f"{row.get('end_date') or ''}|"
            f"{row.get('title') or ''}|"
            f"{row.get('company') or ''}"
        )
    for row in education:
        lines.append(
            "edu|"
            f"{row.get('id') or ''}|"
            f"{row.get('start_date') or ''}|"
            f"{row.get('end_date') or ''}|"
            f"{row.get('degree') or ''}|"
            f"{row.get('institution') or ''}"
        )
    for row in certificates:
        lines.append(
            "cert|"
            f"{row.get('id') or ''}|"
            f"{row.get('issued_at') or ''}|"
            f"{row.get('title') or ''}|"
            f"{row.get('issuer') or ''}"
        )
    payload = "\n".join(sorted(lines))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def combine_fingerprints(*parts: str) -> str:
    """Combine component fingerprints into a single cache key hash."""
    payload = "|".join(p.strip() for p in parts if p and p.strip())
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def compute_skill_fingerprint(kg_repository: Any, person_id: str) -> str:
    """Fingerprint from the person's effective skill set (direct + finished projects)."""
    skills = await kg_repository.get_person_skills(person_id)
    return fingerprint_from_skills(list(skills or []))


async def compute_cv_fingerprint(kg_repository: Any, person_id: str) -> str:
    """Skill fingerprint plus chronology so CV cache invalidates on bio history edits."""
    skill_fp = await compute_skill_fingerprint(kg_repository, person_id)

    employment = await kg_repository.query(
        """
        MATCH (p:Person {id: $person_id})-[:WORKED_AT]->(e:Employment)
        RETURN properties(e) AS row
        """,
        {"person_id": person_id},
    )
    education = await kg_repository.query(
        """
        MATCH (p:Person {id: $person_id})-[:STUDIED_AT]->(e:Education)
        RETURN properties(e) AS row
        """,
        {"person_id": person_id},
    )
    certificates = await kg_repository.query(
        """
        MATCH (p:Person {id: $person_id})-[:HAS_CERTIFICATE]->(c:Certificate)
        RETURN properties(c) AS row
        """,
        {"person_id": person_id},
    )

    chrono_fp = fingerprint_from_chronology(
        [dict(r.get("row") or {}) for r in employment],
        [dict(r.get("row") or {}) for r in education],
        [dict(r.get("row") or {}) for r in certificates],
    )
    return combine_fingerprints(skill_fp, chrono_fp)
