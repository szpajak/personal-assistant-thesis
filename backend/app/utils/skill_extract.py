"""Rule-based skill extraction from job descriptions (no LLM)."""

from __future__ import annotations

import re
from typing import Iterable

from .skill_ids import (
    SKILL_ALIASES,
    canonicalize_skill_list,
    resolve_canonical_skill_name,
)


def seed_required_skills(
    stored_skills: Iterable[str] | None,
    description: str,
    known_skill_names: Iterable[str] | None = None,
) -> list[str]:
    """Return stored skills when present; otherwise extract via regex heuristics.

    This is the cheap, LLM-free seed used at scrape/list/match time so staging
    listings can show estimated overlap before a job is promoted.
    """
    skills = canonicalize_skill_list(
        [str(skill).strip() for skill in (stored_skills or []) if str(skill).strip()]
    )
    if skills or not (description or "").strip():
        return skills
    return canonicalize_skill_list(
        extract_skills_from_text(description, known_skill_names)
    )


def extract_skills_from_text(
    description: str,
    known_skill_names: Iterable[str] | None = None,
    *,
    max_skills: int = 25,
) -> list[str]:
    """Intersect description tokens / phrases against known skills + synonyms."""
    text = (description or "").lower()
    if not text.strip():
        return []

    found: list[str] = []
    seen: set[str] = set()

    def _add(name: str) -> None:
        canonical = resolve_canonical_skill_name(name)
        key = canonical.strip().lower()
        if not key or key in seen:
            return
        seen.add(key)
        found.append(canonical)

    # Known KG skill names (longest first so "Node.js" beats "Node").
    known = sorted(
        {str(n).strip() for n in (known_skill_names or []) if str(n).strip()},
        key=len,
        reverse=True,
    )
    for name in known:
        pattern = re.compile(rf"(?<![a-z0-9]){re.escape(name.lower())}(?![a-z0-9])")
        if pattern.search(text):
            _add(name)
        if len(found) >= max_skills:
            return found

    # Canonical display names from the synonym table. Some (e.g. "Python")
    # are not themselves alias keys, and the looser word boundary still
    # matches a name at the end of a sentence ("Kubernetes.").
    canonicals = sorted(
        {str(name).strip() for name in SKILL_ALIASES.values() if str(name).strip()},
        key=len,
        reverse=True,
    )
    for name in canonicals:
        pattern = re.compile(rf"(?<![a-z0-9]){re.escape(name.lower())}(?![a-z0-9])")
        if pattern.search(text):
            _add(name)
        if len(found) >= max_skills:
            return found

    # Shared synonym map from skill_ids (single source of truth).
    for alias, canonical in sorted(
        SKILL_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True
    ):
        pattern = re.compile(rf"(?<![a-z0-9+#.]){re.escape(alias)}(?![a-z0-9+#.])")
        if pattern.search(text):
            _add(canonical)
        if len(found) >= max_skills:
            break

    return found
