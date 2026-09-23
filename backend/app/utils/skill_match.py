"""Deterministic skill-name overlap used as a fallback when LLM matching fails."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillMatchResult:
    match_score: int
    matching_skills: list[str]
    missing_skills: list[str]


def compute_skill_match(
    user_skills: list[str],
    job_skills: list[str],
) -> SkillMatchResult:
    """Return overlap percentage of required job skills present in the user set.

    Matching is case-insensitive. Returned skill names keep the job's casing.
    Score is ``round(100 * matched / required)``, or ``0`` when the job lists
    no skills.
    """
    if not job_skills:
        return SkillMatchResult(match_score=0, matching_skills=[], missing_skills=[])

    user_keys = {
        skill.strip().lower() for skill in user_skills if skill and skill.strip()
    }
    matching: list[str] = []
    missing: list[str] = []

    for skill in job_skills:
        if not isinstance(skill, str) or not skill.strip():
            continue
        if skill.strip().lower() in user_keys:
            matching.append(skill.strip())
        else:
            missing.append(skill.strip())

    required_count = len(matching) + len(missing)
    if required_count == 0:
        return SkillMatchResult(match_score=0, matching_skills=[], missing_skills=[])

    score = round(100 * len(matching) / required_count)
    return SkillMatchResult(
        match_score=score,
        matching_skills=sorted(matching, key=str.lower),
        missing_skills=sorted(missing, key=str.lower),
    )
