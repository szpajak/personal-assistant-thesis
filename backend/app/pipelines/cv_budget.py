"""Python-side curation of CV evidence, run BEFORE the single LLM tailoring
call in :class:`app.pipelines.cv_pipeline.CVPipeline`.

GraphRAG's :meth:`app.kg.graphrag.GraphRAG.retrieve` returns ranked
Project/Skill/Certificate hits for a job offer; a real candidate portfolio
easily has 8-10 projects and 40-60 skills once several years of experience
and job history accumulate, which is both too much for the CV to read well
and too much for the LLM prompt to stay focused on what actually matters for
THIS job. This module turns the ranked hits (plus the job's REQUIRES skills
and the person's full HAS_SKILL list) into a small, job-relevant "budget" -
a handful of projects, a capped skill list, and 0-2 certificates - entirely
in Python, so the curation is deterministic and auditable rather than left
to the LLM to (unreliably) self-select from a giant dump.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MAX_PROJECTS = 4
MAX_SKILLS = 18
MIN_SKILLS_ANCHOR = 12
MAX_CERTIFICATES = 2


@dataclass
class CVBudget:
    """Curated subset of the person's portfolio to ground this one CV."""

    projects: list[dict[str, Any]] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    certificates: list[dict[str, Any]] = field(default_factory=list)


def _sorted_by_recency(projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Most-recent-first, treating a missing/unparsable ``start_date`` as the
    oldest possible so well-dated projects always win over undated ones.
    """

    def _key(proj: dict[str, Any]) -> str:
        return str(proj.get("end_date") or proj.get("start_date") or "")

    return sorted(projects, key=_key, reverse=True)


def _hit_ids(hits: list[dict[str, Any]], label: str) -> list[str]:
    """Node ids for a given label from ranked retrieval hits, best-rank first."""
    ids: list[str] = []
    seen: set[str] = set()
    for hit in hits:
        if hit.get("label") != label:
            continue
        node_id = str((hit.get("node") or {}).get("id") or "")
        if node_id and node_id not in seen:
            seen.add(node_id)
            ids.append(node_id)
    return ids


def build_cv_budget(
    *,
    retrieval_hits: list[dict[str, Any]],
    all_projects: list[dict[str, Any]],
    all_skills: list[dict[str, Any]],
    all_certificates: list[dict[str, Any]],
    job_required_skills: list[dict[str, Any]],
) -> CVBudget:
    """Select the projects/skills/certificates worth putting in front of the
    LLM for this specific job offer.

    Args:
        retrieval_hits: Ranked hits from ``GraphRAG.retrieve(...,
            labels=["Project", "Skill", "Certificate"], label_preset="cv")``.
        all_projects: The person's full ``PRODUCED`` project list (raw KG
            node properties, each expected to carry ``id``/``title``/
            ``tech_stack``).
        all_skills: The person's full flat skill list (``HAS_SKILL``, each
            with ``id``/``name``/``category``).
        all_certificates: The person's certificates, each additionally
            carrying a ``validated_skills`` list of skill names (see
            ``CVPipeline.fetch_static_profile``).
        job_required_skills: The job's ``REQUIRES`` skills, each with at
            least a ``name``.

    Returns:
        A :class:`CVBudget` capped at ``MAX_PROJECTS`` projects,
        ``MAX_SKILLS`` skills, and ``MAX_CERTIFICATES`` certificates.

    """
    projects_by_id = {str(p.get("id")): p for p in all_projects if p.get("id")}

    required_skill_names_lower = {
        str(rs.get("name") or "").strip().lower()
        for rs in job_required_skills
        if rs.get("name")
    }

    selected_ids = _select_project_ids(
        retrieval_hits=retrieval_hits,
        projects_by_id=projects_by_id,
        all_projects=all_projects,
        required_skill_names_lower=required_skill_names_lower,
    )
    selected_projects = [projects_by_id[pid] for pid in selected_ids if pid in projects_by_id]

    selected_skills = _select_skills(
        retrieval_hits=retrieval_hits,
        selected_projects=selected_projects,
        all_skills=all_skills,
        required_skill_names_lower=required_skill_names_lower,
    )

    selected_certs = _select_certificates(
        retrieval_hits=retrieval_hits,
        all_certificates=all_certificates,
        required_skill_names_lower=required_skill_names_lower,
    )

    return CVBudget(
        projects=selected_projects,
        skills=selected_skills,
        certificates=selected_certs,
    )


def _select_project_ids(
    *,
    retrieval_hits: list[dict[str, Any]],
    projects_by_id: dict[str, dict[str, Any]],
    all_projects: list[dict[str, Any]],
    required_skill_names_lower: set[str],
) -> list[str]:
    """Top-ranked project hits, capped at MAX_PROJECTS; force-include one
    additional (non-hit) project if it is the ONLY project that covers a
    required skill no already-selected project covers.
    """
    ranked_ids = [pid for pid in _hit_ids(retrieval_hits, "Project") if pid in projects_by_id]
    selected_ids = ranked_ids[:MAX_PROJECTS]

    if not selected_ids and all_projects:
        # No retrieval signal at all (e.g. a thin portfolio, or an embedding/
        # retrieval hiccup) - a CV with zero projects is worse than one with
        # unranked-but-real ones, so fall back to the most recent projects
        # rather than leaving the "Projects" section empty.
        selected_ids = [
            str(p.get("id"))
            for p in _sorted_by_recency(all_projects)[:MAX_PROJECTS]
            if p.get("id")
        ]

    def _project_skill_names(proj: dict[str, Any]) -> set[str]:
        return {str(s).strip().lower() for s in (proj.get("tech_stack") or []) if str(s).strip()}

    covered = set()
    for pid in selected_ids:
        covered |= _project_skill_names(projects_by_id[pid])
    uncovered_required = required_skill_names_lower - covered

    if uncovered_required:
        for proj in all_projects:
            pid = str(proj.get("id") or "")
            if not pid or pid in selected_ids:
                continue
            proj_skills = _project_skill_names(proj)
            newly_covered = proj_skills & uncovered_required
            if newly_covered:
                selected_ids.append(pid)
                uncovered_required -= newly_covered
                break

    return selected_ids


def _select_skills(
    *,
    retrieval_hits: list[dict[str, Any]],
    selected_projects: list[dict[str, Any]],
    all_skills: list[dict[str, Any]],
    required_skill_names_lower: set[str],
) -> list[str]:
    """Union of: skills USED by the selected projects, retrieved Skill hits,
    (REQUIRES ∩ HAS_SKILL), and "anchor" skills (the person's programming
    languages, which are foundational enough to always show regardless of
    this specific job) - capped at MAX_SKILLS, backfilled up to
    MIN_SKILLS_ANCHOR from the remaining skill list if still thin.
    """
    ordered_names: list[str] = []
    seen_keys: set[str] = set()

    def _add(name: str) -> None:
        key = name.strip().lower()
        if not key or key in seen_keys:
            return
        seen_keys.add(key)
        ordered_names.append(name.strip())

    for proj in selected_projects:
        for name in proj.get("tech_stack") or []:
            _add(str(name))

    skills_by_id = {str(s.get("id")): s for s in all_skills if s.get("id")}
    for hit_id in _hit_ids(retrieval_hits, "Skill"):
        skill = skills_by_id.get(hit_id)
        if skill and skill.get("name"):
            _add(str(skill["name"]))

    for skill in all_skills:
        name = str(skill.get("name") or "")
        if name.lower() in required_skill_names_lower:
            _add(name)

    for skill in all_skills:
        name = str(skill.get("name") or "")
        if str(skill.get("category") or "").strip().lower() == "language":
            _add(name)

    if len(ordered_names) < MIN_SKILLS_ANCHOR:
        for skill in all_skills:
            if len(ordered_names) >= MIN_SKILLS_ANCHOR:
                break
            _add(str(skill.get("name") or ""))

    return ordered_names[:MAX_SKILLS]


def _select_certificates(
    *,
    retrieval_hits: list[dict[str, Any]],
    all_certificates: list[dict[str, Any]],
    required_skill_names_lower: set[str],
) -> list[dict[str, Any]]:
    """0-2 certificates that either validate a required skill or were
    themselves surfaced by retrieval - never the full certificate list, so a
    person with many certificates doesn't bloat every CV with irrelevant ones.
    """
    hit_ids = set(_hit_ids(retrieval_hits, "Certificate"))
    selected: list[dict[str, Any]] = []
    for cert in all_certificates:
        cert_id = str(cert.get("id") or "")
        validated = {
            str(s).strip().lower() for s in (cert.get("validated_skills") or []) if str(s).strip()
        }
        relevant = (cert_id and cert_id in hit_ids) or bool(validated & required_skill_names_lower)
        if relevant:
            selected.append(cert)
        if len(selected) >= MAX_CERTIFICATES:
            break
    return selected
