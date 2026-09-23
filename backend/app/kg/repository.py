from __future__ import annotations

import logging
import re
from typing import Any

from ..core.neo4j import get_neo4j_driver

logger = logging.getLogger(__name__)

# Lucene boolean queries explode past IndexSearcher.maxClauseCount (1024)
# when a full job description is passed as a free-text query: each token
# becomes a clause. Clip to a short term list before escaping.
_LUCENE_MAX_TERMS = 40
_LUCENE_SPECIAL = re.compile(r'([+\-!(){}\[\]^"~*?:\\/])')


def prepare_lucene_query(
    query_text: str, max_terms: int = _LUCENE_MAX_TERMS
) -> str:
    """Collapse a free-text string into a short, escaped Lucene query.

    Full job descriptions (thousands of tokens) must never be sent to
    ``db.index.fulltext.queryNodes`` - they hit ``TooManyClauses``.
    """
    if not query_text or not str(query_text).strip():
        return ""
    tokens = re.findall(r"[A-Za-z0-9+#.]{2,}", str(query_text))
    if not tokens:
        tokens = str(query_text).split()
    clipped = " ".join(tokens[:max_terms])
    return _LUCENE_SPECIAL.sub(r"\\\1", clipped)


class KGRepository:
    """Knowledge Graph repository for managing nodes and relationships in Neo4j."""

    async def upsert_node(
        self,
        label: str,
        properties: dict[str, Any],
    ) -> str:
        """Upsert a node in the knowledge graph using MERGE.

        Args:
            label: Node label (e.g., 'Person', 'Skill', 'Project')
            properties: Dictionary of node properties (must include 'id' key)

        Returns:
            Node ID from properties

        """
        driver = get_neo4j_driver()
        node_id = properties.get("id", "")

        # Labels cannot be parameterized in Cypher, so we use string formatting
        # but the properties are parameterized.
        query = f"""
        MERGE (node:{label} {{id: $node_id}})
        SET node += $props
        RETURN node.id as id
        """

        async with driver.session() as session:
            result = await session.run(query, node_id=node_id, props=properties)
            record = await result.single()
            return str(record["id"] if record else node_id)

    async def upsert_relationship(
        self,
        from_label: str,
        from_id: str,
        relationship_type: str,
        to_label: str,
        to_id: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Upsert a relationship between two nodes using MERGE.

        Args:
            from_label: Source node label
            from_id: Source node ID
            relationship_type: Type of relationship (e.g., 'HAS_SKILL')
            to_label: Target node label
            to_id: Target node ID
            properties: Optional relationship properties

        """
        driver = get_neo4j_driver()
        rel_props = properties or {}

        query = f"""
        MATCH (from:{from_label} {{id: $from_id}})
        MATCH (to:{to_label} {{id: $to_id}})
        MERGE (from)-[rel:{relationship_type}]->(to)
        SET rel += $props
        RETURN rel
        """

        async with driver.session() as session:
            await session.run(
                query,
                from_id=from_id,
                to_id=to_id,
                props=rel_props,
            )

    async def vector_search(
        self,
        label: str,
        embedding: list[float],
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Perform vector similarity search in Neo4j.

        Args:
            label: Node label to search over
            embedding: Query embedding vector
            top_k: Number of results to return (default 10)

        Returns:
            List of nodes with similarity scores

        """
        # A degraded embedder returns an all-zero vector. Neo4j's vector index
        # rejects vectors with a non-positive L2-norm, so skip the query rather
        # than letting it raise.
        if not embedding or not any(embedding):
            return []

        driver = get_neo4j_driver()
        index_name = f"{label.lower()}_embedding_index"

        # Requires Neo4j vector index to be created first
        query = """
        CALL db.index.vector.queryNodes($index_name, $top_k, $embedding)
        YIELD node, score
        RETURN properties(node) as node, score, labels(node)[0] as label
        """

        async with driver.session() as session:
            result = await session.run(
                query, index_name=index_name, embedding=embedding, top_k=top_k
            )
            records = await result.data()
            return records

    async def fulltext_search(
        self,
        label: str,
        query_text: str,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Perform a Lucene full-text search in Neo4j (lexical retrieval channel).

        Args:
            label: Node label to search over
            query_text: Free-text query
            top_k: Number of results to return

        Returns:
            List of nodes with relevance scores (same shape as :meth:`vector_search`)

        """
        if not query_text or not query_text.strip():
            return []

        driver = get_neo4j_driver()
        index_name = f"{label.lower()}_fulltext_index"
        escaped = prepare_lucene_query(query_text)
        if not escaped:
            return []

        query = """
        CALL db.index.fulltext.queryNodes($index_name, $query_text, {limit: $top_k})
        YIELD node, score
        RETURN properties(node) as node, score, labels(node)[0] as label
        """

        try:
            async with driver.session() as session:
                result = await session.run(
                    query, index_name=index_name, query_text=escaped, top_k=top_k
                )
                return await result.data()
        except Exception:
            # Missing index (label never had a fulltext index created) or a
            # still-malformed query - degrade to vector-only rather than fail.
            return []

    async def count_nodes(self, label: str) -> int:
        """Count nodes of a given label (cheap existence check before a
        vector/full-text search channel is worth querying).
        """
        driver = get_neo4j_driver()
        query = f"MATCH (n:{label}) RETURN count(n) as count"
        async with driver.session() as session:
            result = await session.run(query)
            record = await result.single()
            return int(record["count"]) if record else 0

    async def get_person_subgraph_ids(self, person_id: str) -> dict[str, set[str]]:
        """Return the IDs of personal-data nodes owned by/connected to a person.

        Used to scope GraphRAG retrieval so multi-person KGs never surface
        one person's private Project/Skill/Certificate/LearningResource nodes
        in another person's context. Shared/market data (JobOffer, Company)
        is intentionally NOT scoped here - callers keep those unrestricted.
        """
        driver = get_neo4j_driver()
        query = """
        MATCH (p:Person {id: $person_id})
        OPTIONAL MATCH (p)-[:HAS_SKILL]->(s:Skill)
        OPTIONAL MATCH (p)-[:PRODUCED]->(pr:Project)
        OPTIONAL MATCH (pr)-[:USES]->(ps:Skill)
        OPTIONAL MATCH (p)-[:HAS_CERTIFICATE]->(c:Certificate)
        OPTIONAL MATCH (p)-[:RECOMMENDED]->(lr:LearningResource)
        RETURN
            collect(DISTINCT s.id) + collect(DISTINCT ps.id) AS skill_ids,
            collect(DISTINCT pr.id) AS project_ids,
            collect(DISTINCT c.id) AS certificate_ids,
            collect(DISTINCT lr.id) AS learning_resource_ids
        """
        async with driver.session() as session:
            result = await session.run(query, person_id=person_id)
            record = await result.single()
            if not record:
                return {
                    "Skill": set(),
                    "Project": set(),
                    "Certificate": set(),
                    "LearningResource": set(),
                }
            return {
                "Skill": {sid for sid in record["skill_ids"] if sid},
                "Project": {pid for pid in record["project_ids"] if pid},
                "Certificate": {cid for cid in record["certificate_ids"] if cid},
                "LearningResource": {
                    lid for lid in record["learning_resource_ids"] if lid
                },
            }

    async def find_related_nodes_typed(
        self,
        start_label: str,
        start_id: str,
        hops: int = 1,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Find related nodes along with the relationship type/props that
        connect them, for structured (not just neighbor-name) context packing.

        Returns a list of ``{"node": {...}, "relationship_type": str,
        "relationship_props": {...}, "direction": "out"|"in"}`` dicts.
        """
        driver = get_neo4j_driver()
        query = f"""
        MATCH (start:{start_label} {{id: $start_id}})
        MATCH (start)-[rel*1..{hops}]-(related)
        WHERE related <> start
        WITH related, rel[0] AS first_rel, startNode(rel[0]) AS rel_start
        RETURN DISTINCT
            properties(related) AS node,
            labels(related)[0] AS label,
            type(first_rel) AS relationship_type,
            properties(first_rel) AS relationship_props,
            CASE WHEN rel_start.id = $start_id THEN 'out' ELSE 'in' END AS direction
        LIMIT $limit
        """

        async with driver.session() as session:
            result = await session.run(query, start_id=start_id, limit=limit)
            return await result.data()

    async def record_skill_demand_snapshot(self) -> int:
        """Compute today's demand (count of career JobOffers requiring each
        skill) and write one dated ``SkillDemandSnapshot`` node per skill,
        building a demand time series over successive nightly runs.

        Idempotent per day: re-running on the same date updates the same
        snapshot node instead of creating duplicates (deterministic ID).

        Returns:
            Number of snapshot nodes written.

        """
        driver = get_neo4j_driver()
        query = """
        MATCH (j:JobOffer)-[:REQUIRES]->(s:Skill)
        WHERE j.purpose IS NULL OR j.purpose <> 'market_sample'
        WITH s, count(DISTINCT j) AS demand
        WITH s, demand, toString(date()) AS today
        MERGE (snap:SkillDemandSnapshot {id: s.id + '_' + today})
        SET snap.skill_id = s.id, snap.demand_count = demand, snap.snapshot_date = today
        MERGE (s)-[:DEMAND_SNAPSHOT]->(snap)
        RETURN count(snap) AS snapshot_count
        """
        async with driver.session() as session:
            result = await session.run(query)
            record = await result.single()
            return int(record["snapshot_count"]) if record else 0

    async def get_skill_demand_history(
        self, skill_id: str, limit: int = 30
    ) -> list[dict[str, Any]]:
        """Return the most recent demand snapshots for a skill, oldest first
        (ready to feed a trend chart).
        """
        driver = get_neo4j_driver()
        query = """
        MATCH (:Skill {id: $skill_id})-[:DEMAND_SNAPSHOT]->(snap:SkillDemandSnapshot)
        RETURN snap.snapshot_date AS date, snap.demand_count AS demand
        ORDER BY snap.snapshot_date DESC
        LIMIT $limit
        """
        async with driver.session() as session:
            result = await session.run(query, skill_id=skill_id, limit=limit)
            rows = await result.data()
            return list(reversed(rows))

    async def find_near_duplicate_skills(
        self, similarity_threshold: float = 0.93
    ) -> list[dict[str, Any]]:
        """Find pairs of distinct Skill nodes whose embeddings are near-identical
        (cosine similarity above ``similarity_threshold``) but were not caught
        by the static alias table - candidates for
        :meth:`merge_skill_nodes`.

        Only compares skills that actually have an embedding (see
        ``KGIngestion._upsert_skill_preserving_existing``).
        """
        driver = get_neo4j_driver()
        query = """
        MATCH (a:Skill), (b:Skill)
        WHERE a.id < b.id
          AND a.embedding IS NOT NULL AND b.embedding IS NOT NULL
        WITH a, b, vector.similarity.cosine(a.embedding, b.embedding) AS similarity
        WHERE similarity >= $threshold
        RETURN a.id AS source_id, a.name AS source_name,
               b.id AS target_id, b.name AS target_name,
               similarity
        ORDER BY similarity DESC
        """
        try:
            async with driver.session() as session:
                result = await session.run(query, threshold=similarity_threshold)
                return await result.data()
        except Exception:
            # vector.similarity.cosine requires Neo4j 5.13+; degrade gracefully
            # on older deployments rather than crashing the Celery job.
            return []

    async def merge_skill_nodes(self, source_id: str, target_id: str) -> None:
        """Merge ``source_id`` into ``target_id``: repoint every relationship
        from the source Skill onto the target, record the source's name as an
        alias on the target, and delete the source node.

        Uses Neo4j's ``apoc.refactor.mergeNodes`` when available (correctly
        merges relationships of any type/direction in one call); falls back
        to a manual HAS_SKILL/USES/REQUIRES/VALIDATES/TEACHES repoint when
        APOC isn't installed.
        """
        driver = get_neo4j_driver()
        async with driver.session() as session:
            try:
                await session.run(
                    """
                    MATCH (source:Skill {id: $source_id}), (target:Skill {id: $target_id})
                    SET target.aliases = apoc.coll.toSet(
                        coalesce(target.aliases, []) + coalesce(source.aliases, []) + [source.name]
                    )
                    WITH source, target
                    CALL apoc.refactor.mergeNodes([target, source], {
                        properties: 'discard', mergeRels: true
                    }) YIELD node
                    RETURN node
                    """,
                    source_id=source_id,
                    target_id=target_id,
                )
                return
            except Exception:
                logger.info(
                    "apoc.refactor.mergeNodes unavailable, falling back to manual "
                    "skill merge for %s -> %s",
                    source_id,
                    target_id,
                )

            for rel_type, direction in [
                ("HAS_SKILL", "in"),
                ("USES", "in"),
                ("REQUIRES", "in"),
                ("USED_IN_ROLE", "in"),
                ("VALIDATES", "in"),
                ("TEACHES", "in"),
            ]:
                pattern = (
                    f"(other)-[r:{rel_type}]->(source)"
                    if direction == "in"
                    else f"(source)-[r:{rel_type}]->(other)"
                )
                merge_pattern = (
                    f"(other)-[:{rel_type}]->(target)"
                    if direction == "in"
                    else f"(target)-[:{rel_type}]->(other)"
                )
                await session.run(
                    f"""
                    MATCH (source:Skill {{id: $source_id}}), (target:Skill {{id: $target_id}})
                    MATCH {pattern}
                    MERGE {merge_pattern}
                    DELETE r
                    """,
                    source_id=source_id,
                    target_id=target_id,
                )

            await session.run(
                """
                MATCH (source:Skill {id: $source_id}), (target:Skill {id: $target_id})
                SET target.aliases = coalesce(target.aliases, []) + coalesce(source.aliases, []) + [source.name]
                WITH source
                DETACH DELETE source
                """,
                source_id=source_id,
                target_id=target_id,
            )

    async def get_node(
        self,
        label: str,
        node_id: str,
    ) -> dict[str, Any] | None:
        """Retrieve a node from the knowledge graph.

        Args:
            label: Node label
            node_id: Node ID to retrieve

        Returns:
            Dictionary of node properties, or None if not found

        """
        driver = get_neo4j_driver()

        query = f"""
        MATCH (node:{label} {{id: $node_id}})
        RETURN properties(node) as props
        """

        async with driver.session() as session:
            result = await session.run(query, node_id=node_id)
            record = await result.single()
            return record["props"] if record else None

    async def query(
        self,
        cypher: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query against the knowledge graph.

        Args:
            cypher: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records

        """
        driver = get_neo4j_driver()
        params = parameters or {}

        async with driver.session() as session:
            result = await session.run(cypher, **params)
            records = await result.data()
            return records

    async def list_skill_names(self, limit: int = 500) -> list[str]:
        """Return Skill.node display names for heuristic extraction."""
        rows = await self.query(
            "MATCH (s:Skill) RETURN s.name AS name LIMIT $limit",
            {"limit": limit},
        )
        return [
            str(row.get("name") or "").strip()
            for row in rows
            if row.get("name")
        ]

    async def delete_node(
        self,
        label: str,
        node_id: str,
    ) -> None:
        """Delete a node from the knowledge graph.

        Args:
            label: Node label
            node_id: Node ID to delete

        """
        driver = get_neo4j_driver()

        query = f"""
        MATCH (node:{label} {{id: $node_id}})
        DETACH DELETE node
        """

        async with driver.session() as session:
            await session.run(query, node_id=node_id)

    async def find_related_nodes(
        self,
        start_label: str,
        start_id: str,
        relationship_type: str | None = None,
        hops: int = 1,
    ) -> list[dict[str, Any]]:
        """Find nodes related to a given node.

        Args:
            start_label: Starting node label
            start_id: Starting node ID
            relationship_type: Optional relationship type to filter on
            hops: Number of relationship hops (default 1)

        Returns:
            List of related nodes

        """
        driver = get_neo4j_driver()

        # Build the relationship pattern.
        # If type is provided, use :TYPE, otherwise just empty (any relation)
        rel_pattern = f":{relationship_type}" if relationship_type else ""

        query = f"""
        MATCH (start:{start_label} {{id: $start_id}})
        MATCH (start)-[{rel_pattern}*1..{hops}]-(related)
        RETURN DISTINCT properties(related) as node
        """

        async with driver.session() as session:
            result = await session.run(query, start_id=start_id)
            records = await result.data()
            return [r["node"] for r in records]

    async def get_person_skills(self, person_id: str) -> list[dict[str, Any]]:
        """Return all skills for a person, direct and via finished projects.

        Skills attached to ``planned`` / ``in_progress`` projects are excluded
        until the project status becomes ``finished``. Legacy projects with
        NULL status are treated as finished so pre-existing skillsets do not
        regress. Finishing a project also MERGEs ``HAS_SKILL`` (see
        ``ensure_has_skill_for_finished_projects``); the USES path remains as
        a safety net for older graphs.
        """
        driver = get_neo4j_driver()

        query = """
        MATCH (p:Person {id: $person_id})
        OPTIONAL MATCH (p)-[:HAS_SKILL]->(direct:Skill)
        OPTIONAL MATCH (p)-[:PRODUCED]->(proj:Project)-[:USES]->(from_project:Skill)
        WHERE proj.status IS NULL OR proj.status = 'finished'
        WITH collect(DISTINCT direct) + collect(DISTINCT from_project) AS skill_nodes
        UNWIND skill_nodes AS s
        WITH s WHERE s IS NOT NULL
        RETURN DISTINCT properties(s) AS node
        """

        async with driver.session() as session:
            result = await session.run(query, person_id=person_id)
            records = await result.data()
            return [r["node"] for r in records]

    async def get_person_career_brief(self, person_id: str) -> dict[str, Any]:
        """Return a structured career profile for job matching: finished
        projects, employment, certificates, and education, each annotated
        with the skills evidenced by that node via typed edges.

        Unlike :meth:`get_person_skills` (a flat skill list) or GraphRAG
        similarity search, this is a direct, deterministic walk of the
        person's own subgraph - appropriate when the candidate (``person_id``)
        is already known and no retrieval/ranking is needed. Used by
        ``JobMatchPipeline`` to ground LLM justifications in real evidence
        instead of a job-independent vector search.

        Returns a dict with keys ``projects``, ``employment``,
        ``certificates``, ``education`` - each a list of plain dicts. Missing
        Person or empty categories yield empty lists, never an error.
        """
        driver = get_neo4j_driver()

        query = """
        MATCH (p:Person {id: $person_id})
        CALL {
            WITH p
            OPTIONAL MATCH (p)-[:PRODUCED]->(proj:Project)
            WHERE proj IS NOT NULL
              AND (proj.status IS NULL OR proj.status = 'finished')
            OPTIONAL MATCH (proj)-[:USES]->(ps:Skill)
            WITH proj, collect(DISTINCT ps.name) AS skills
            WHERE proj IS NOT NULL
            RETURN collect({
                title: proj.title,
                seniority: proj.seniority,
                start_date: proj.start_date,
                end_date: proj.end_date,
                description: proj.description,
                skills: skills
            }) AS projects
        }
        CALL {
            WITH p
            OPTIONAL MATCH (p)-[:WORKED_AT]->(emp:Employment)
            WHERE emp IS NOT NULL
            OPTIONAL MATCH (emp)-[:USED_IN_ROLE]->(es:Skill)
            WITH emp, collect(DISTINCT es.name) AS skills
            WHERE emp IS NOT NULL
            RETURN collect({
                title: emp.title,
                company: emp.company,
                start_date: emp.start_date,
                end_date: emp.end_date,
                description: emp.description,
                skills: skills
            }) AS employment
        }
        CALL {
            WITH p
            OPTIONAL MATCH (p)-[:HAS_CERTIFICATE]->(c:Certificate)
            WHERE c IS NOT NULL
            OPTIONAL MATCH (c)-[:VALIDATES]->(cs:Skill)
            WITH c, collect(DISTINCT cs.name) AS skills
            WHERE c IS NOT NULL
            RETURN collect({
                title: c.title,
                issuer: c.issuer,
                issued_at: c.issued_at,
                skills: skills
            }) AS certificates
        }
        CALL {
            WITH p
            OPTIONAL MATCH (p)-[:STUDIED_AT]->(edu:Education)
            WHERE edu IS NOT NULL
            RETURN collect({
                degree: edu.degree,
                field_of_study: edu.field_of_study,
                institution: edu.institution,
                start_date: edu.start_date,
                end_date: edu.end_date
            }) AS education
        }
        RETURN projects, employment, certificates, education
        """

        async with driver.session() as session:
            result = await session.run(query, person_id=person_id)
            record = await result.single()
            if not record:
                return {"projects": [], "employment": [], "certificates": [], "education": []}
            return {
                "projects": list(record.get("projects") or []),
                "employment": list(record.get("employment") or []),
                "certificates": list(record.get("certificates") or []),
                "education": list(record.get("education") or []),
            }

    async def ensure_has_skill_for_finished_projects(
        self,
        person_id: str,
        project_id: str | None = None,
    ) -> int:
        """MERGE ``HAS_SKILL`` for skills evidenced by finished projects.

        Finishing a portfolio project means the person acquired those skills.
        Existing ``HAS_SKILL`` edges (e.g. from certificates) are left intact
        (``ON CREATE`` only). Returns the number of skills that received a new
        or already-existing ownership edge from this match set.
        """
        driver = get_neo4j_driver()

        query = """
        MATCH (p:Person {id: $person_id})-[:PRODUCED]->(proj:Project)-[uses:USES]->(s:Skill)
        WHERE (proj.status IS NULL OR proj.status = 'finished')
          AND ($project_id IS NULL OR proj.id = $project_id)
        MERGE (p)-[r:HAS_SKILL]->(s)
        ON CREATE SET
          r.source = 'project',
          r.confidence = coalesce(uses.confidence, 1.0),
          r.project_id = proj.id
        RETURN count(DISTINCT s) AS skill_count
        """

        async with driver.session() as session:
            result = await session.run(
                query, person_id=person_id, project_id=project_id
            )
            record = await result.single()
            return int(record["skill_count"]) if record else 0

    async def get_market_demand(self, limit: int = 10) -> list[dict[str, Any]]:
        """Query the KG for skills most required in career JobOffer nodes.

        Excludes ``market_sample`` offers (auto-scraped TargetRole context -
        see ``KGIngestion.ingest_market_sample_job``) so the global "whole
        market" view only reflects jobs the user actually saved/promoted.

        Args:
            limit: Maximum number of skills to return

        Returns:
            List of dictionaries with 'name' and 'demand' count

        """
        driver = get_neo4j_driver()

        query = """
        MATCH (s:Skill)<-[:REQUIRES]-(j:JobOffer)
        WHERE j.purpose IS NULL OR j.purpose <> 'market_sample'
        RETURN s.name as name, count(j) as demand
        ORDER BY demand DESC
        LIMIT $limit
        """

        async with driver.session() as session:
            result = await session.run(query, limit=limit)
            return await result.data()

    async def get_target_role_sample_job_ids(self, role_id: str) -> list[str]:
        """Return the ids of a TargetRole's currently-sampled JobOffers."""
        rows = await self.query(
            """
            MATCH (t:TargetRole {id: $role_id})-[:SAMPLED]->(j:JobOffer)
            RETURN j.id AS id
            """,
            {"role_id": role_id},
        )
        return [str(row["id"]) for row in rows if row.get("id")]

    async def get_target_role_sample_stats(self, role_id: str) -> list[dict[str, Any]]:
        """Aggregate REQUIRES demand over exactly this role's sampled
        JobOffers - the real "similar postings" market signal a TargetRole's
        skill-gap analysis is benchmarked against (see
        ``skill_analysis_pipeline._fetch_target_role_market_data``).
        """
        return await self.query(
            """
            MATCH (t:TargetRole {id: $role_id})-[:SAMPLED]->(j:JobOffer)-[r:REQUIRES]->(s:Skill)
            WITH s.name AS name, count(DISTINCT j) AS demand, collect(r.level) AS levels
            RETURN name, demand, levels
            ORDER BY demand DESC
            """,
            {"role_id": role_id},
        )

    async def vector_search_within(
        self,
        label: str,
        node_ids: list[str],
        embedding: list[float],
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Cosine-similarity search restricted to an explicit id allow-list.

        The global vector index (``db.index.vector.queryNodes``, see
        :meth:`vector_search`) has no id filter, so when the searchable
        universe is already known and small (e.g. a TargetRole's ~50
        sampled JobOffers) this runs ``vector.similarity.cosine`` directly
        instead, guaranteeing unrelated same-label nodes elsewhere in the KG
        can never be returned.
        """
        if not embedding or not any(embedding) or not node_ids:
            return []

        driver = get_neo4j_driver()
        query = f"""
        MATCH (node:{label})
        WHERE node.id IN $node_ids AND node.embedding IS NOT NULL
        WITH node, vector.similarity.cosine(node.embedding, $embedding) AS score
        RETURN properties(node) AS node, score, labels(node)[0] AS label
        ORDER BY score DESC
        LIMIT $top_k
        """

        async with driver.session() as session:
            result = await session.run(
                query, node_ids=node_ids, embedding=embedding, top_k=top_k
            )
            return await result.data()

    async def get_job_by_url(self, url: str) -> dict[str, Any] | None:
        """Retrieve a career JobOffer by its canonical URL."""
        return await self.get_node_by_url("JobOffer", url)

    async def get_node_by_url(self, label: str, url: str) -> dict[str, Any] | None:
        """Retrieve a node of the given label by URL."""
        if not url:
            return None

        driver = get_neo4j_driver()
        query = f"""
        MATCH (j:{label} {{url: $url}})
        RETURN properties(j) as props
        """

        async with driver.session() as session:
            result = await session.run(query, url=url)
            record = await result.single()
            return record["props"] if record else None

    async def get_job_or_listing(self, job_id: str) -> tuple[dict[str, Any] | None, str | None]:
        """Return ``(props, "career")`` for a promoted JobOffer id, or
        ``(None, None)`` when it doesn't exist (or is only a market_sample
        stub - those aren't the user's own jobs; callers fall back to the
        Postgres staging copy for matching/promotion).

        Scraped-but-not-promoted listings live in Postgres now (see
        ``JobListingRepository``) - callers that need to resolve a "staging"
        tier id must check there themselves.
        """
        offer = await self.get_node("JobOffer", job_id)
        if offer and str(offer.get("purpose") or "career") != "market_sample":
            return offer, "career"
        return None, None

    async def delete_outgoing_relationships(
        self,
        from_label: str,
        from_id: str,
        relationship_type: str,
    ) -> None:
        """Delete all outgoing relationships of a given type from a node."""
        driver = get_neo4j_driver()
        query = f"""
        MATCH (from:{from_label} {{id: $from_id}})-[rel:{relationship_type}]->()
        DELETE rel
        """

        async with driver.session() as session:
            await session.run(query, from_id=from_id)

    async def backfill_job_offer_properties(self) -> None:
        """Ensure legacy JobOffer nodes have status defaults."""
        driver = get_neo4j_driver()
        query = """
        MATCH (j:JobOffer)
        SET j.status = coalesce(j.status, 'active')
        """

        async with driver.session() as session:
            await session.run(query)
