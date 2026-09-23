"""Graph Retrieval-Augmented Generation service for semantic search over KG."""

from __future__ import annotations

import json
from typing import Any

from ..kg.chains import create_job_matching_chain, create_skill_extraction_chain
from ..kg.repository import KGRepository
from .embeddings import KGEmbeddings

# Personal-data labels are scoped to the querying person's subgraph before
# fusion (see KGRepository.get_person_subgraph_ids) so a multi-person KG
# never leaks one person's evidence into another's retrieval. JobOffer is
# shared market data and is intentionally left unscoped.
_PERSONAL_LABELS = {"Project", "Skill", "Certificate"}

# Reciprocal Rank Fusion constant. 60 is the standard default from the
# original RRF paper (Cormack et al.) and TREC baselines - large enough to
# avoid overweighting rank-1 hits from either channel, small enough that
# rank still matters more than raw (differently-scaled) vector/lexical scores.
_RRF_K = 60

# Per-pipeline label priors so e.g. CV generation biases toward
# Project/Skill evidence while job matching also wants JobOffer context.
# Multiplies each node's fused RRF score before the final top_k cut.
LABEL_WEIGHT_PRESETS: dict[str, dict[str, float]] = {
    "default": {"Project": 1.0, "Skill": 1.0, "JobOffer": 1.0, "Certificate": 1.0},
    "cv": {"Project": 1.4, "Skill": 1.2, "JobOffer": 0.6, "Certificate": 1.1},
    "job_match": {"Project": 1.1, "Skill": 1.3, "JobOffer": 0.9, "Certificate": 0.8},
    "skill_gap": {"Project": 1.0, "Skill": 1.4, "JobOffer": 0.7, "Certificate": 0.9},
}


def _rrf_fuse(
    *rank_lists: list[dict[str, Any]],
    k: int = _RRF_K,
) -> list[dict[str, Any]]:
    """Fuse multiple ranked result lists (vector, full-text, ...) via
    Reciprocal Rank Fusion: score(node) = sum(1 / (k + rank_in_list)).

    Each item must carry ``node.id`` and ``label``. Returns fused items
    sorted by descending RRF score, each annotated with ``rrf_score``.
    """
    scores: dict[str, float] = {}
    payload: dict[str, dict[str, Any]] = {}

    for rank_list in rank_lists:
        for rank, item in enumerate(rank_list, start=1):
            node = item.get("node") or {}
            node_id = node.get("id")
            label = item.get("label", "Unknown")
            if not node_id:
                continue
            key = f"{label}:{node_id}"
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            payload.setdefault(key, item)

    fused = [{**payload[key], "rrf_score": score} for key, score in scores.items()]
    fused.sort(key=lambda x: x["rrf_score"], reverse=True)
    return fused


class GraphRAG:
    """Graph Retrieval-Augmented Generation for semantic search over KG."""

    def __init__(
        self,
        kg_repository: KGRepository,
        embeddings: KGEmbeddings,
    ) -> None:
        """Initialize GraphRAG with dependencies.

        Args:
            kg_repository: Knowledge graph repository
            embeddings: Embeddings service

        """
        self.kg_repository = kg_repository
        self.embeddings = embeddings

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        hops: int = 1,
        person_id: str | None = None,
        label_preset: str = "default",
        labels: list[str] | None = None,
        hybrid: bool = True,
    ) -> list[dict[str, Any]]:
        """Hybrid (vector + full-text, RRF-fused) retrieval returning ranked
        hits, each expanded with its typed neighbors - the structured result
        curator pipelines (CV budgeting, per-job match evidence, target-role
        skill gap) select from, as opposed to :meth:`assemble_context`'s
        flattened string for pipelines that just want to hand raw context to
        an LLM.

        Args:
            query: User query to find context for
            top_k: Number of top results to return
            hops: Number of relationship hops to traverse for each hit's
                "related" neighbors (0 skips expansion entirely)
            person_id: When given, scopes personal-data labels (Project,
                Skill, Certificate) to this person's subgraph so multi-person
                KGs don't cross-contaminate retrieval. Shared data (JobOffer)
                is never scoped.
            label_preset: One of :data:`LABEL_WEIGHT_PRESETS` - biases which
                node types are favored for this pipeline.
            labels: Explicit allow-list of node labels to search, overriding
                the default ``["Project", "Skill", "JobOffer", "Certificate"]``
                set. Callers that must never surface a label (e.g. CV/job
                match excluding ``JobOffer``, or a skill-gap target-role query
                that should ONLY search ``JobOffer``) pass this instead of
                relying on the preset's weighting to merely de-prioritize it.
            hybrid: When True (production default), fuse vector and Lucene
                full-text lists with RRF. When False, rank by the vector
                channel only - used by the Chapter 5 retrieval ablation.

        Returns:
            Ranked hits, each ``{"label": str, "node": dict, "rrf_score":
            float, "weighted_score": float, "related": list[dict]}`` where
            ``related`` mirrors :meth:`KGRepository.find_related_nodes_typed`.

        """
        embedding = await self.embeddings.embed_text(query)
        weights = LABEL_WEIGHT_PRESETS.get(label_preset, LABEL_WEIGHT_PRESETS["default"])

        if labels is not None:
            labels_to_search = list(labels)
        else:
            labels_to_search = ["Project", "Skill", "JobOffer"]
            if await self.kg_repository.count_nodes("Certificate") > 0:
                labels_to_search.append("Certificate")

        person_scope: dict[str, set[str]] | None = None
        if person_id:
            person_scope = await self.kg_repository.get_person_subgraph_ids(person_id)

        vector_results: list[dict[str, Any]] = []
        fulltext_results: list[dict[str, Any]] = []
        for label in labels_to_search:
            v_results = await self.kg_repository.vector_search(
                label=label, embedding=embedding, top_k=top_k * 2
            )
            f_results: list[dict[str, Any]] = []
            if hybrid:
                f_results = await self.kg_repository.fulltext_search(
                    label=label, query_text=query, top_k=top_k * 2
                )
            if person_scope is not None and label in _PERSONAL_LABELS:
                allowed_ids = person_scope.get(label, set())
                v_results = [r for r in v_results if (r.get("node") or {}).get("id") in allowed_ids]
                f_results = [r for r in f_results if (r.get("node") or {}).get("id") in allowed_ids]
            vector_results.extend(v_results)
            fulltext_results.extend(f_results)

        fused = (
            _rrf_fuse(vector_results, fulltext_results)
            if hybrid
            else _rrf_fuse(vector_results)
        )
        for item in fused:
            item["weighted_score"] = item["rrf_score"] * weights.get(item.get("label", ""), 1.0)
        fused.sort(key=lambda x: x["weighted_score"], reverse=True)
        top_results = fused[:top_k]

        for result in top_results:
            node = result.get("node") or {}
            label = result.get("label", "Unknown")
            node_id = node.get("id")
            if hops > 0 and node_id:
                result["related"] = await self.kg_repository.find_related_nodes_typed(
                    start_label=label, start_id=node_id, hops=hops, limit=8
                )
            else:
                result["related"] = []

        return top_results

    async def retrieve_scoped(
        self,
        query: str,
        node_ids: list[str],
        top_k: int = 8,
        hops: int = 0,
        label: str = "JobOffer",
    ) -> list[dict[str, Any]]:
        """Hybrid retrieval like :meth:`retrieve`, but pre-scoped to an
        explicit id allow-list instead of the whole ``label`` population.

        Used when the searchable universe is already known and small (e.g.
        a TargetRole's sampled JobOffers): a plain :meth:`retrieve` call
        ranks against *every* node with that label first, so the ~50
        relevant ids could easily lose to unrelated postings elsewhere in
        the KG and never surface after a post-hoc intersection. The vector
        channel here queries only ``node_ids``
        (:meth:`KGRepository.vector_search_within`); the full-text channel
        has no id filter, so it's over-fetched and filtered down instead.
        """
        if not node_ids:
            return []

        embedding = await self.embeddings.embed_text(query)
        vector_hits = await self.kg_repository.vector_search_within(
            label, node_ids, embedding, top_k=top_k
        )
        fulltext_hits = await self.kg_repository.fulltext_search(
            label, query, top_k=max(top_k * 4, 50)
        )
        allowed = set(node_ids)
        fulltext_hits = [
            hit for hit in fulltext_hits if (hit.get("node") or {}).get("id") in allowed
        ]

        fused = _rrf_fuse(vector_hits, fulltext_hits)
        top_results = fused[:top_k]

        for result in top_results:
            node = result.get("node") or {}
            node_id = node.get("id")
            if hops > 0 and node_id:
                result["related"] = await self.kg_repository.find_related_nodes_typed(
                    start_label=label, start_id=node_id, hops=hops, limit=8
                )
            else:
                result["related"] = []

        return top_results

    async def assemble_context(
        self,
        query: str,
        top_k: int = 5,
        hops: int = 1,
        person_id: str | None = None,
        label_preset: str = "default",
        max_chars: int = 12000,
        labels: list[str] | None = None,
    ) -> str:
        """Assemble context from KG for a given query using hybrid retrieval.

        Thin string formatter over :meth:`retrieve` - see that method for the
        structured-hit shape and full parameter docs (including ``labels``).

        Args:
            max_chars: Final safety-net cap on assembled context length, not
                the real limiter - retrieval breadth (top_k, hops, the
                per-node property/related-node caps below) determines how
                much of the graph is actually used.

        Returns:
            Assembled context as string

        """
        top_results = await self.retrieve(
            query,
            top_k=top_k,
            hops=hops,
            person_id=person_id,
            label_preset=label_preset,
            labels=labels,
        )

        context_parts = [
            f"Query: {query}",
            f"Retrieved {len(top_results)} relevant nodes (hybrid vector + full-text):",
        ]
        for i, result in enumerate(top_results, 1):
            node = result.get("node", {})
            label = result.get("label", "Unknown")
            node_id = node.get("id", "N/A")
            node_title = node.get("title", node.get("name", "Untitled"))

            context_parts.append(
                f"{i}. [{label}] [Score: {result['weighted_score']:.4f}] "
                f"{node_title} (ID: {node_id})"
            )

            props_str = ", ".join(
                f"{k}: {v}"
                for k, v in node.items()
                if k not in ["embedding", "id", "title", "name"]
            )
            if props_str:
                # Still bounded per-node (a single runaway field shouldn't
                # dominate the context), just not as stingily as before.
                if len(props_str) > 1200:
                    props_str = props_str[:1200] + "…"
                context_parts.append(f"   Properties: {props_str}")

            for rel in result.get("related") or []:
                rel_node = rel.get("node") or {}
                rel_name = rel_node.get("title", rel_node.get("name", "N/A"))
                rel_type = rel.get("relationship_type", "RELATED_TO")
                rel_props = rel.get("relationship_props") or {}
                props_suffix = ""
                if rel_props:
                    props_suffix = " (" + ", ".join(
                        f"{k}: {v}" for k, v in rel_props.items()
                    ) + ")"
                context_parts.append(
                    f"   Connected via {rel_type}{props_suffix}: {rel_name}"
                )

        context = "\n".join(context_parts)
        if max_chars > 0 and len(context) > max_chars:
            return context[:max_chars] + "…"
        return context

    async def assemble_evidence_chain(
        self,
        person_id: str,
        skill_name: str,
        top_k: int = 3,
    ) -> str:
        """Multi-hop template: for a given skill, trace Person -> Project ->
        Skill (and Certificate -> VALIDATES -> Skill) evidence chains.

        Used to ground specific CV bullet points ("prove" a claimed skill
        with the concrete projects/certificates that demonstrate it) rather
        than relying on a single-hop neighbor list.
        """
        from ..utils.skill_ids import canonical_skill_id

        skill_id = canonical_skill_id(skill_name)
        rows = await self.kg_repository.query(
            """
            MATCH (p:Person {id: $person_id})
            OPTIONAL MATCH (p)-[:PRODUCED]->(proj:Project)-[uses:USES]->(s:Skill {id: $skill_id})
            OPTIONAL MATCH (p)-[:HAS_CERTIFICATE]->(cert:Certificate)-[:VALIDATES]->(s)
            OPTIONAL MATCH (p)-[:WORKED_AT]->(emp:Employment)-[:USED_IN_ROLE]->(s)
            RETURN
                collect(DISTINCT {title: proj.title, confidence: uses.confidence}) AS projects,
                collect(DISTINCT cert.title) AS certificates,
                collect(DISTINCT emp.title + ' at ' + emp.company) AS roles
            """,
            {"person_id": person_id, "skill_id": skill_id},
        )
        if not rows:
            return f"No evidence found for skill '{skill_name}'."

        row = rows[0]
        projects = [p for p in (row.get("projects") or []) if p.get("title")][:top_k]
        certificates = [c for c in (row.get("certificates") or []) if c][:top_k]
        roles = [r for r in (row.get("roles") or []) if r][:top_k]

        parts = [f"Evidence chain for skill '{skill_name}':"]
        if projects:
            proj_str = "; ".join(
                f"{p['title']} (confidence: {p.get('confidence', 'n/a')})" for p in projects
            )
            parts.append(f"  Demonstrated in projects: {proj_str}")
        if roles:
            parts.append(f"  Used in roles: {', '.join(roles)}")
        if certificates:
            parts.append(f"  Validated by certificates: {', '.join(certificates)}")
        if len(parts) == 1:
            parts.append("  No direct evidence in the KG yet.")
        return "\n".join(parts)

    async def summarize_project_themes(
        self,
        person_id: str,
        min_projects: int = 6,
        similarity_threshold: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Lightweight "community summary" over a person's projects, grouping
        by shared-skill Jaccard similarity instead of full Leiden community
        detection - the roadmap explicitly defers real graph-community
        GraphRAG until the KG is dense enough to justify it (see
        ``kg_graphrag_roadmap`` Phase 2: "Defer full Leiden community GraphRAG
        until graph is denser").

        Returns an empty list below ``min_projects`` (theming a handful of
        projects isn't meaningful) so callers can conditionally enrich
        "theme"-style queries (e.g. "what kind of work do you do?") only once
        there's enough of a corpus for it to add value.
        """
        rows = await self.kg_repository.query(
            """
            MATCH (p:Person {id: $person_id})-[:PRODUCED]->(proj:Project)
            OPTIONAL MATCH (proj)-[:USES]->(s:Skill)
            RETURN proj.id AS id, proj.title AS title, collect(DISTINCT s.name) AS skills
            """,
            {"person_id": person_id},
        )
        if len(rows) < min_projects:
            return []

        projects = [
            {
                "id": row["id"],
                "title": row["title"],
                "skills": {s for s in (row["skills"] or []) if s},
            }
            for row in rows
        ]

        clusters: list[dict[str, Any]] = []
        used: set[str] = set()

        for i, project in enumerate(projects):
            if project["id"] in used or not project["skills"]:
                continue

            cluster = [project]
            cluster_skills = set(project["skills"])
            for other in projects[i + 1 :]:
                if other["id"] in used or not other["skills"]:
                    continue
                overlap = cluster_skills & other["skills"]
                union = cluster_skills | other["skills"]
                jaccard = len(overlap) / len(union) if union else 0.0
                if jaccard >= similarity_threshold:
                    cluster.append(other)
                    cluster_skills |= other["skills"]

            if len(cluster) >= 2:
                for member in cluster:
                    used.add(member["id"])
                top_skills = sorted(cluster_skills)[:5]
                theme_label = " / ".join(top_skills[:3]) or "General"
                titles = [member["title"] for member in cluster]
                clusters.append(
                    {
                        "theme": theme_label,
                        "project_titles": titles,
                        "shared_skills": top_skills,
                        "summary": (
                            f"{len(cluster)} projects centered on {theme_label}: "
                            f"{', '.join(titles)}."
                        ),
                    }
                )

        return clusters

    async def retrieve_relevant_skills(
        self,
        job_title: str,
        top_k: int = 10,
    ) -> list[str]:
        """Retrieve skills relevant to a job title using LLM extraction.

        Args:
            job_title: Job title to find skills for
            top_k: Number of skills to retrieve

        Returns:
            List of relevant skill names

        """
        chain = create_skill_extraction_chain()

        # Use LLM to infer skills from job title
        response = await chain.ainvoke({"text": job_title})

        try:
            # Parse LLM response
            skills_data = json.loads(str(response.content))
            skill_names = [s.get("name", "") for s in skills_data[:top_k]]
            return skill_names
        except (json.JSONDecodeError, AttributeError, TypeError):
            # Fallback to keyword extraction
            return job_title.split()[:top_k]

    async def retrieve_related_projects(
        self,
        skill_id: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Retrieve projects related to a skill.

        Args:
            skill_id: Skill ID to find projects for
            top_k: Number of projects to retrieve

        Returns:
            List of project records

        """
        projects = await self.kg_repository.find_related_nodes(
            start_label="Skill",
            start_id=skill_id,
            relationship_type="USES",
            hops=1,
        )
        return projects[:top_k]

    async def match_candidate_to_job(
        self,
        candidate_skills: list[str],
        job_description: str,
    ) -> dict[str, Any]:
        """Match candidate skills against job requirements using LLM.

        Args:
            candidate_skills: List of candidate skill names
            job_description: Job posting description

        Returns:
            Match analysis with score and recommendations

        """
        chain = create_job_matching_chain()

        response = await chain.ainvoke(
            {
                "job_requirements": job_description,
                "candidate_skills": ", ".join(candidate_skills),
            }
        )

        try:
            match_data = json.loads(str(response.content))
            return dict(match_data)
        except (json.JSONDecodeError, AttributeError, TypeError):
            return {
                "match_score": 0,
                "matching_skills": [],
                "missing_skills": [],
                "strengths": [],
                "development_areas": [],
            }
