"""Zaveri-style intrinsic KG quality checks against Dataset A."""

from __future__ import annotations

from typing import Any

from app.kg.repository import KGRepository
from app.utils.skill_ids import canonical_skill_id, resolve_canonical_skill_name
from eval.dataset_a import (
    ER_CLUSTERS,
    ER_MUST_STAY_APART,
    EXPECTED_HAS_SKILL,
    MUST_NOT_HAS_SKILL,
    PERSON_A,
    PERSON_B,
    PROJECTS,
    REQUIRED_LABELS,
    REQUIRED_RELS,
)
from eval.metrics import set_prf


async def _label_counts(repo: KGRepository) -> dict[str, int]:
    rows = await repo.query("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS c")
    return {str(r["label"]): int(r["c"]) for r in rows if r.get("label")}


async def _rel_types(repo: KGRepository) -> set[str]:
    rows = await repo.query("MATCH ()-[r]->() RETURN DISTINCT type(r) AS t")
    return {str(r["t"]) for r in rows if r.get("t")}


async def run_constraint_queries(repo: KGRepository) -> dict[str, int]:
    checks = {
        "orphan_skills": ("MATCH (s:Skill) WHERE NOT (s)--() RETURN count(s) AS c"),
        "unowned_projects": (
            "MATCH (p:Project) WHERE NOT (p)<-[:PRODUCED]-(:Person) "
            "RETURN count(p) AS c"
        ),
        "missing_uses": (
            "MATCH (p:Project) WHERE NOT (p)-[:USES]->(:Skill) RETURN count(p) AS c"
        ),
        "duplicate_skill_ids": (
            "MATCH (s:Skill) WITH s.id AS id, count(*) AS c "
            "WHERE c > 1 RETURN count(id) AS c"
        ),
        "person_a_flutter_has_skill": (
            "MATCH (p:Person {id: $pid})-[:HAS_SKILL]->(s:Skill) "
            "WHERE toLower(s.name) IN ['flutter', 'dart', 'rust'] "
            "RETURN count(s) AS c"
        ),
    }
    out: dict[str, int] = {}
    for name, cypher in checks.items():
        rows = await repo.query(cypher, {"pid": PERSON_A})
        out[name] = int(rows[0]["c"]) if rows else 0
    return out


async def inject_dirt(repo: KGRepository) -> None:
    """Known violations so maintenance checks have a non-zero before-state."""
    await repo.upsert_node(
        "Skill",
        {
            "id": "eval_orphan_skill",
            "name": "OrphanEvalSkill",
            "category": "technical",
            "level": "beginner",
        },
    )
    await repo.upsert_node(
        "Project",
        {
            "id": "eval_unowned_project",
            "title": "Unowned",
            "description": "No PRODUCED edge",
            "status": "finished",
        },
    )


async def clean_dirt(repo: KGRepository) -> None:
    await repo.query(
        "MATCH (n) WHERE n.id IN $ids DETACH DELETE n",
        {"ids": ["eval_orphan_skill", "eval_unowned_project"]},
    )


def _er_results(handles: dict[str, str]) -> dict[str, Any]:
    clusters: dict[str, list[str]] = {}
    for canonical, aliases in ER_CLUSTERS.items():
        ids = sorted({canonical_skill_id(a) for a in aliases})
        clusters[canonical] = ids
    collapsed = {name: len(ids) == 1 for name, ids in clusters.items()}
    apart = []
    for left, right in ER_MUST_STAY_APART:
        apart.append(
            {
                "pair": [left, right],
                "distinct": canonical_skill_id(left) != canonical_skill_id(right),
            }
        )
    return {
        "clusters": clusters,
        "collapsed": collapsed,
        "must_stay_apart": apart,
        "pairwise_correct": all(collapsed.values())
        and all(item["distinct"] for item in apart),
        "observed_skill_ids": {
            name: handles.get(f"skill:{name}") for name in ER_CLUSTERS
        },
    }


async def evaluate_kg_quality(
    repo: KGRepository,
    id_map: dict[str, Any],
) -> dict[str, Any]:
    labels = await _label_counts(repo)
    rels = await _rel_types(repo)
    schema_label = len(REQUIRED_LABELS & set(labels)) / len(REQUIRED_LABELS)
    schema_rel = len(REQUIRED_RELS & rels) / len(REQUIRED_RELS)

    rows = await repo.get_person_skills(PERSON_A)
    held = {
        resolve_canonical_skill_name(str(r.get("name") or ""))
        for r in rows
        if r.get("name")
    }
    skill_prf = set_prf(held, set(EXPECTED_HAS_SKILL))
    leaked = sorted(held & MUST_NOT_HAS_SKILL)

    python_row = next(
        (
            r
            for r in rows
            if resolve_canonical_skill_name(str(r.get("name"))) == "Python"
        ),
        {},
    )
    python_level = str(python_row.get("level") or "")

    baseline = await run_constraint_queries(repo)
    await inject_dirt(repo)
    dirty = await run_constraint_queries(repo)
    await clean_dirt(repo)
    restored = await run_constraint_queries(repo)

    finished = sum(1 for spec in PROJECTS.values() if spec["status"] == "finished")
    owned = await repo.query(
        "MATCH (:Person {id: $pid})-[:PRODUCED]->(p:Project) RETURN count(p) AS c",
        {"pid": PERSON_A},
    )
    population_projects = (owned[0]["c"] if owned else 0) / max(len(PROJECTS), 1)

    return {
        "schema_completeness_labels": schema_label,
        "schema_completeness_relationships": schema_rel,
        "label_counts": labels,
        "relationship_types": sorted(rels),
        "population_projects_person_a": population_projects,
        "finished_projects_specified": finished,
        "has_skill": {
            **skill_prf,
            "held": sorted(held),
            "leaked_forbidden": leaked,
            "python_level": python_level,
            "python_not_downgraded": python_level == "expert",
        },
        "entity_resolution": _er_results(id_map.get("handles") or {}),
        "consistency": {
            "clean_seed": baseline,
            "after_dirt": dirty,
            "after_cleanup": restored,
            "dirt_detected": dirty["orphan_skills"] >= 1
            and dirty["unowned_projects"] >= 1,
        },
        "person_b_present": bool(
            await repo.get_node("Person", PERSON_B)
            or await repo.get_node("Person", id_map.get("person_b", PERSON_B))
        ),
    }
