from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

from ...dependencies import get_current_user
from ...kg.embeddings import KGEmbeddings
from ...kg.graphrag import GraphRAG
from ...kg.repository import KGRepository
from ...models.user import User
from ...utils.neo4j_types import neo4j_to_python

router = APIRouter()
logger = logging.getLogger(__name__)


def _node_display_label(node: dict[str, Any]) -> str:
    return str(node.get("name", node.get("title", node.get("id", ""))))


def _append_node(
    nodes: list[dict[str, Any]],
    node_ids: set[str],
    node_props: dict[str, Any],
    node_type: str,
) -> None:
    """Add a node to the graph payload if it has not been seen yet."""
    props = neo4j_to_python(node_props)
    node_id = props.get("id")
    if not node_id or node_id in node_ids:
        return

    nodes.append(
        {
            "id": node_id,
            "type": node_type,
            "data": {
                "label": _node_display_label(props),
                "properties": props,
            },
        }
    )
    node_ids.add(node_id)


_EVIDENCE_RELS = {"USES", "VALIDATES", "USED_IN_ROLE"}


def _attach_skill_metrics(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    owned_skill_ids: set[str] | None = None,
) -> None:
    """Annotate Skill nodes with demand, evidence, and ownership flags.

    Ownership matches Skills tab ``get_person_skills`` (direct HAS_SKILL plus
    skills evidenced by finished projects) when ``owned_skill_ids`` is provided.
    Falls back to HAS_SKILL edges alone for callers that omit it.
    """
    demand: dict[str, int] = {}
    evidence: dict[str, int] = {}
    direct: set[str] = set()
    for edge in edges:
        label = edge.get("label")
        target = edge.get("target")
        if not isinstance(target, str):
            continue
        if label == "REQUIRES":
            demand[target] = demand.get(target, 0) + 1
        elif label in _EVIDENCE_RELS:
            evidence[target] = evidence.get(target, 0) + 1
        elif label == "HAS_SKILL":
            direct.add(target)

    owned = owned_skill_ids if owned_skill_ids is not None else direct

    for node in nodes:
        if node.get("type") != "Skill":
            continue
        props = node.setdefault("data", {}).setdefault("properties", {})
        node_id = node.get("id")
        if not isinstance(node_id, str):
            continue
        props["demand_count"] = demand.get(node_id, 0)
        props["evidence_count"] = evidence.get(node_id, 0)
        props["has_direct_link"] = node_id in owned


@router.get("/stats")
async def get_stats(
    current_user: User = Depends(get_current_user),
    repo: KGRepository = Depends(),
) -> dict[str, Any]:
    """Get dashboard statistics for a person."""
    person_id = f"user_{current_user.id}"
    try:
        # Count projects
        projects = await repo.find_related_nodes(
            start_label="Person",
            start_id=person_id,
            relationship_type="PRODUCED",
        )

        # Same definition as Skills tab "My skills"
        skills = await repo.get_person_skills(person_id)

        # Count applications
        apps = await repo.find_related_nodes(
            start_label="Person",
            start_id=person_id,
            relationship_type="APPLIED_TO",
        )

        # Count job matches
        offers = await repo.query("MATCH (j:JobOffer) RETURN count(j) as count")

        return {
            "active_projects": len(projects),
            "skills_tracked": len(skills),
            "open_applications": len(apps),
            "job_matches": offers[0]["count"] if offers else 0,
        }
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {
            "active_projects": 0,
            "skills_tracked": 0,
            "open_applications": 0,
            "job_matches": 0,
        }


@router.get("/themes")
async def get_project_themes(
    current_user: User = Depends(get_current_user),
    repo: KGRepository = Depends(),
) -> dict[str, Any]:
    """Lightweight "community summary" of the person's projects, grouped by
    shared skills (see ``GraphRAG.summarize_project_themes``). Full Leiden
    community detection is deliberately deferred until the graph is denser -
    this Jaccard-similarity heuristic is enough to answer "what kind of work
    do you do?"-style queries once there are a handful of projects.
    """
    person_id = f"user_{current_user.id}"
    graph_rag = GraphRAG(kg_repository=repo, embeddings=KGEmbeddings(kg_repository=repo))
    themes = await graph_rag.summarize_project_themes(person_id)
    return {"themes": themes}


@router.get("/graph")
async def get_graph(
    current_user: User = Depends(get_current_user),
    repo: KGRepository = Depends(),
) -> dict[str, Any]:
    """Get the full knowledge graph for a person."""
    person_id = f"user_{current_user.id}"
    try:
        person = await repo.get_node("Person", person_id)
        if not person:
            return {"nodes": [], "edges": []}

        # Return each relationship with its type and true endpoints instead of
        # inferring them from variable-length paths (which lost rel.type in
        # Python serialization and mis-attributed 2-hop edges to Person).
        query = """
        MATCH (p:Person {id: $person_id})-[r]->(n)
        WHERE NOT n:SkillDemandSnapshot
        RETURN type(r) AS rel_type,
               properties(r) AS rel_props,
               startNode(r).id AS source_id,
               endNode(r).id AS target_id,
               properties(startNode(r)) AS source_node,
               labels(startNode(r))[0] AS source_label,
               properties(endNode(r)) AS target_node,
               labels(endNode(r))[0] AS target_label
        UNION
        MATCH (p:Person {id: $person_id})-->(mid)-[r]->(n)
        WHERE NOT n:SkillDemandSnapshot AND NOT mid:SkillDemandSnapshot
        RETURN type(r) AS rel_type,
               properties(r) AS rel_props,
               startNode(r).id AS source_id,
               endNode(r).id AS target_id,
               properties(startNode(r)) AS source_node,
               labels(startNode(r))[0] AS source_label,
               properties(endNode(r)) AS target_node,
               labels(endNode(r))[0] AS target_label
        """
        results = await repo.query(query, parameters={"person_id": person_id})

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        node_ids: set[str] = set()
        edge_ids: set[str] = set()

        _append_node(nodes, node_ids, person, "Person")

        for row in results:
            rel_type = row.get("rel_type")
            source_id = row.get("source_id")
            target_id = row.get("target_id")
            if not rel_type or not source_id or not target_id:
                continue
            if row.get("source_label") == "SkillDemandSnapshot":
                continue
            if row.get("target_label") == "SkillDemandSnapshot":
                continue

            _append_node(
                nodes, node_ids, row["source_node"], row.get("source_label", "Unknown")
            )
            _append_node(
                nodes, node_ids, row["target_node"], row.get("target_label", "Unknown")
            )

            edge_id = f"rel_{source_id}_{target_id}_{rel_type}"
            if edge_id in edge_ids:
                continue

            edges.append(
                {
                    "id": edge_id,
                    "source": source_id,
                    "target": target_id,
                    "label": rel_type,
                    "properties": neo4j_to_python(row.get("rel_props") or {}),
                }
            )
            edge_ids.add(edge_id)

        owned_skills = await repo.get_person_skills(person_id)
        owned_ids = {
            str(s["id"])
            for s in owned_skills
            if isinstance(s, dict) and s.get("id")
        }
        _attach_skill_metrics(nodes, edges, owned_skill_ids=owned_ids)

        return {
            "nodes": nodes,
            "edges": edges,
            "person_id": person_id,
            "person_name": str(person.get("name") or person.get("email") or ""),
        }
    except Exception as e:
        logger.error(f"Failed to get graph: {e}")
        return {"nodes": [], "edges": []}
