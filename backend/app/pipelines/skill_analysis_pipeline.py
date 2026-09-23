"""Pipeline for analyzing skill gaps (Python/Cypher, no LLM) and, separately,
generating an LLM learning roadmap from a chosen skill/project set."""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from ..config import settings
from ..kg.chains import get_chat_llm
from ..kg.embeddings import KGEmbeddings
from ..kg.graphrag import GraphRAG
from ..kg.ingestion import KGIngestion
from ..kg.repository import KGRepository
from ..prompts.skill_prompts import LEARNING_ROADMAP_PROMPT, SUGGESTED_PROJECTS_PROMPT
from ..utils.llm_json import RobustJsonOutputParser
from ..utils.skill_ids import skill_level_rank

logger = logging.getLogger(__name__)

# The global "market demand" aggregate scans every career JobOffer, so it's
# capped to the skills that actually show up most often - a long tail of
# one-off mentions isn't useful gap-analysis signal.
_MAX_MARKET_SKILLS = 20
# How many of a TargetRole's top sampled postings to ground the LLM roadmap
# prompt in (see _format_role_postings) - a short digest, not the whole ~50.
_MAX_ROLE_POSTING_HITS = 8
# Bounds how many gaps get surfaced to the response - with ~50 sampled
# offers the raw diff could easily list every skill the candidate doesn't
# have; keep it to the highest-demand/most-impactful ones.
_MAX_HARD_GAPS = 12


class SkillAnalysisState(TypedDict):
    """State for the (LLM-free) skill-gap analysis pipeline."""

    user_id: str
    target_role_id: str | None
    target_role_title: str | None
    target_role_ready: bool
    sample_status: str | None
    sample_job_count: int
    user_skills: list[str]
    user_skill_levels: dict[str, str]
    market_skill_stats: list[dict[str, Any]]
    hard_gaps: list[dict[str, Any]]
    analysis_result: dict[str, Any]


def _typical_level(levels: list[Any] | None) -> str | None:
    """Most common recognized ``REQUIRES.level`` among a skill's postings.

    Ties broken toward the higher proficiency level (a role that's split
    intermediate/advanced skews toward the more demanding reading).
    """
    counts: dict[str, int] = {}
    for level in levels or []:
        normalized = str(level or "").strip().lower()
        if skill_level_rank(normalized) > 0:
            counts[normalized] = counts.get(normalized, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: (kv[1], skill_level_rank(kv[0])))[0]


def _compute_hard_gaps(
    user_skill_levels: dict[str, str],
    market_skill_stats: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Deterministically diff the candidate's own skills against
    market/target demand - Python, not the LLM, decides what counts as a
    gap (see plan section 4): a skill is either entirely ``missing``, or
    held below the demand's typical proficiency (``underleveled``).
    Skills the candidate already covers at or above that level are left
    out entirely; the LLM only ever sees real, computed gaps.
    """
    hard_gaps: list[dict[str, Any]] = []
    for stat in market_skill_stats:
        name = str(stat.get("name") or "").strip()
        if not name:
            continue
        key = name.lower()
        demand = int(stat.get("demand") or 0)
        expected_level = stat.get("typical_level")
        current_level = user_skill_levels.get(key)

        if current_level is None:
            hard_gaps.append(
                {
                    "skill": name,
                    "kind": "missing",
                    "demand": demand,
                    "current_level": None,
                    "expected_level": expected_level,
                }
            )
        elif expected_level and skill_level_rank(current_level) < skill_level_rank(
            expected_level
        ):
            hard_gaps.append(
                {
                    "skill": name,
                    "kind": "underleveled",
                    "demand": demand,
                    "current_level": current_level,
                    "expected_level": expected_level,
                }
            )

    hard_gaps.sort(key=lambda g: (0 if g["kind"] == "missing" else 1, -g["demand"]))
    return hard_gaps[:_MAX_HARD_GAPS]


def _format_person_brief(brief: dict[str, Any], max_chars: int = 3000) -> str:
    """Short background flavor for the LLM's wording - NOT the source of
    the gaps themselves (those come from :func:`_compute_hard_gaps`).

    Deliberately not a GraphRAG call: the old
    ``assemble_context(f"Skills and experience for user {user_id}")`` was a
    hybrid search with no real query intent (searching the candidate's own
    skill names against their own skills is circular), so this is now a
    direct, cheap read of the same subgraph :class:`JobMatchPipeline` uses
    for its career brief.
    """
    parts: list[str] = []

    employment = brief.get("employment") or []
    roles = [
        f"{e.get('title')} at {e.get('company')}" for e in employment if e.get("title")
    ]
    if roles:
        parts.append("Roles: " + "; ".join(roles))

    projects = brief.get("projects") or []
    titles = [p.get("title") for p in projects if p.get("title")][:10]
    if titles:
        parts.append("Projects: " + ", ".join(titles))

    certificates = brief.get("certificates") or []
    cert_titles = [c.get("title") for c in certificates if c.get("title")]
    if cert_titles:
        parts.append("Certificates: " + ", ".join(cert_titles))

    text = "\n".join(parts)
    if not text:
        return "No career history recorded yet."
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "…"
    return text


def _gap_reason(gap: dict[str, Any]) -> str:
    """Deterministic, templated explanation for a computed gap - no LLM
    call needed just to explain numbers Python already has."""
    demand = int(gap.get("demand") or 0)
    demand_str = f"{demand} tracked offer(s)" if demand else "the tracked offers"
    if gap.get("kind") == "underleveled":
        return (
            f"Current level {gap.get('current_level')} is below the typically "
            f"expected {gap.get('expected_level')} ({demand_str})."
        )
    return f"Missing skill required by {demand_str}."


def build_gap_analysis_result(
    hard_gaps: list[dict[str, Any]],
    user_skills: list[str],
    market_skill_stats: list[dict[str, Any]],
) -> dict[str, Any]:
    """Deterministic gap-analysis payload (skill_gaps + core_strengths) -
    no LLM call, so gaps are available the moment market data is ready
    instead of waiting on a "Generate" click.
    """
    user_skill_names = {skill.strip().lower() for skill in user_skills if skill}
    core_strengths = [
        str(stat["name"])
        for stat in market_skill_stats
        if str(stat.get("name") or "").strip().lower() in user_skill_names
    ]

    skill_gaps = [
        {
            "skill": gap["skill"],
            "gap_reason": _gap_reason(gap),
            "priority": "high" if index < 2 else "medium",
            "kind": str(gap.get("kind") or "missing"),
            "current_level": gap.get("current_level"),
            "expected_level": gap.get("expected_level"),
            "demand": int(gap.get("demand") or 0),
        }
        for index, gap in enumerate(hard_gaps)
    ]

    return {"core_strengths": core_strengths, "skill_gaps": skill_gaps}


def _format_role_postings(hits: list[dict[str, Any]]) -> str:
    """Short digest of GraphRAG-retrieved sampled postings (titles,
    companies, recurring required skills) to ground the roadmap LLM prompt
    in this role's actual market, not a generic title.
    """
    if not hits:
        return ""
    lines = []
    for hit in hits[:_MAX_ROLE_POSTING_HITS]:
        node = hit.get("node") or {}
        title = str(node.get("title") or "").strip()
        company = str(node.get("company") or "").strip()
        skills = [str(s) for s in (node.get("required_skills") or []) if s][:8]
        if not title:
            continue
        line = f"- {title}" + (f" at {company}" if company else "")
        if skills:
            line += f" — requires: {', '.join(skills)}"
        lines.append(line)
    return "\n".join(lines)


def normalize_skill_analysis(result: dict[str, Any]) -> dict[str, Any]:
    """Coerce LLM output (suggested projects only - gaps are computed in
    Python, see :func:`build_gap_analysis_result`) into the shape expected
    by the frontend API.
    """
    normalized_projects: list[dict[str, Any]] = []
    for project in result.get("suggested_projects", []):
        if not isinstance(project, dict):
            continue
        skills_covered = [
            str(s) for s in (project.get("skills_covered") or []) if s
        ]
        tech_stack = [str(t) for t in (project.get("tech_stack") or []) if t]
        key_steps = [
            str(s).strip() for s in (project.get("key_steps") or []) if str(s).strip()
        ]
        deliverables = [
            str(d).strip()
            for d in (project.get("deliverables") or [])
            if str(d).strip()
        ]
        title = str(project.get("title", "")).strip()
        if not title:
            continue
        if not skills_covered and tech_stack:
            skills_covered = list(tech_stack)
        normalized_projects.append(
            {
                "title": title,
                "description": str(project.get("description", "")),
                "tech_stack": tech_stack or skills_covered,
                "skills_covered": skills_covered,
                "key_steps": key_steps,
                "deliverables": deliverables,
            }
        )

    return {"suggested_projects": normalized_projects}


def _fallback_suggested_projects(target_skills: list[str]) -> list[dict[str, Any]]:
    """Deterministic project briefs when the LLM call/parse fails - batches
    the requested skills into up to 3 multi-skill project suggestions."""
    chunk_size = max(1, (len(target_skills) + 2) // 3) if target_skills else 1
    suggested_projects: list[dict[str, Any]] = []
    for index in range(0, len(target_skills), chunk_size):
        chunk = target_skills[index : index + chunk_size]
        if not chunk:
            continue
        suggested_projects.append(
            {
                "title": f"Portfolio project: {', '.join(chunk[:3])}",
                "description": (
                    "Build a realistic end-to-end project that exercises "
                    f"{', '.join(chunk)} together, practicing each skill "
                    "through concrete implementation work."
                ),
                "tech_stack": chunk,
                "skills_covered": chunk,
                "key_steps": [
                    f"Design architecture that requires {chunk[0]}",
                    f"Implement core features using {', '.join(chunk[:3])}",
                    "Document the approach and demo the working result",
                ],
                "deliverables": [
                    "Working prototype or repository",
                    f"Short write-up explaining how {', '.join(chunk)} were applied",
                ],
            }
        )
        if len(suggested_projects) >= 3:
            break
    return suggested_projects


class SkillAnalysisPipeline:
    """LLM-free skill-gap analysis: deterministic gaps/core-strengths from
    the candidate's own skills vs. real market demand (global career offers
    or a specific TargetRole's sampled postings). See
    :class:`LearningRoadmapPipeline` for the (separate, LLM) roadmap step
    and :meth:`suggest_projects_for_skills` for project-brief generation.
    """

    def __init__(
        self,
        kg_repository: KGRepository,
        graph_rag: GraphRAG,
        kg_ingestion: KGIngestion | None = None,
    ) -> None:
        self.kg_repository = kg_repository
        self.graph_rag = graph_rag
        self.kg_ingestion = kg_ingestion or KGIngestion(
            kg_repository=kg_repository,
            embeddings=KGEmbeddings(kg_repository=kg_repository),
            scrape_ttl_days=settings.job_scrape_ttl_days,
        )
        self.llm = get_chat_llm(temperature=0, max_tokens=4000)
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        """Build the LangGraph StateGraph."""
        workflow = StateGraph(SkillAnalysisState)

        workflow.add_node("fetch_user_skills", self.fetch_user_skills)
        workflow.add_node("fetch_market_data", self.fetch_market_data)
        workflow.add_node("compute_hard_gaps", self.compute_hard_gaps)
        workflow.add_node("build_result", self.build_result)

        workflow.set_entry_point("fetch_user_skills")
        workflow.add_edge("fetch_user_skills", "fetch_market_data")
        workflow.add_edge("fetch_market_data", "compute_hard_gaps")
        workflow.add_edge("compute_hard_gaps", "build_result")
        workflow.add_edge("build_result", END)

        return workflow.compile()

    async def fetch_user_skills(self, state: SkillAnalysisState) -> dict[str, Any]:
        """Fetch user skills (with proficiency levels) from KG."""
        user_id = state["user_id"]
        skills = await self.kg_repository.get_person_skills(user_id)
        names: list[str] = []
        levels: dict[str, str] = {}
        for skill in skills:
            name = str(skill.get("name") or "").strip()
            if not name:
                continue
            names.append(name)
            level = str(skill.get("level") or "intermediate").strip().lower()
            levels[name.lower()] = level
        return {"user_skills": names, "user_skill_levels": levels}

    async def fetch_market_data(self, state: SkillAnalysisState) -> dict[str, Any]:
        """Fetch target-skill demand stats (name/demand/typical level):
        either aggregated over a specific :class:`TargetRole`'s sampled
        JobOffers (when ``target_role_id`` is set), or the unscoped
        aggregate market demand across every career offer.
        """
        target_role_id = state.get("target_role_id")
        if target_role_id:
            return await self._fetch_target_role_market_data(target_role_id)
        return await self._fetch_global_market_data()

    async def _fetch_global_market_data(self) -> dict[str, Any]:
        """"Whole market" mode: pure Cypher aggregate, no GraphRAG - "most
        required skills across every career JobOffer" is a plain COUNT,
        not a retrieval problem.
        """
        rows = await self.kg_repository.query(
            """
            MATCH (j:JobOffer)-[r:REQUIRES]->(s:Skill)
            WHERE j.purpose IS NULL OR j.purpose <> 'market_sample'
            WITH s.name AS name, count(DISTINCT j) AS demand, collect(r.level) AS levels
            RETURN name, demand, levels
            ORDER BY demand DESC
            LIMIT $limit
            """,
            {"limit": _MAX_MARKET_SKILLS},
        )
        stats = [
            {
                "name": row["name"],
                "demand": row.get("demand") or 0,
                "typical_level": _typical_level(row.get("levels")),
            }
            for row in rows
            if row.get("name")
        ]
        return {
            "market_skill_stats": stats,
            "target_role_title": None,
            "target_role_ready": True,
            "sample_status": None,
            "sample_job_count": 0,
        }

    async def _fetch_target_role_market_data(
        self, target_role_id: str
    ) -> dict[str, Any]:
        """Target-role mode: demand is aggregated over *all* of this role's
        sampled JobOffers (the ~50 real postings scraped for its
        title/location - see ``app.tasks.role_tasks``), not a GraphRAG
        best-match over an arbitrary title. If the sample isn't ready yet
        (never refreshed, still scraping, or the scrape failed), this
        surfaces that instead of silently falling back to unrelated jobs
        elsewhere in the KG.
        """
        role_rows = await self.kg_repository.query(
            """
            MATCH (t:TargetRole {id: $target_role_id})
            RETURN t.title AS title, t.sample_status AS sample_status,
                   t.sample_job_count AS sample_job_count
            """,
            {"target_role_id": target_role_id},
        )
        if not role_rows:
            return {
                "market_skill_stats": [],
                "target_role_title": None,
                "target_role_ready": False,
                "sample_status": None,
                "sample_job_count": 0,
            }

        row = role_rows[0]
        title = row.get("title")
        sample_status = str(row.get("sample_status") or "idle")
        sample_job_count = int(row.get("sample_job_count") or 0)

        if sample_status != "ready" or sample_job_count == 0:
            return {
                "market_skill_stats": [],
                "target_role_title": title,
                "target_role_ready": False,
                "sample_status": sample_status,
                "sample_job_count": sample_job_count,
            }

        rows = await self.kg_repository.get_target_role_sample_stats(target_role_id)
        stats = [
            {
                "name": row["name"],
                "demand": row.get("demand") or 0,
                "typical_level": _typical_level(row.get("levels")),
            }
            for row in rows
            if row.get("name")
        ]

        return {
            "market_skill_stats": stats,
            "target_role_title": title,
            "target_role_ready": True,
            "sample_status": sample_status,
            "sample_job_count": sample_job_count,
        }

    async def compute_hard_gaps(self, state: SkillAnalysisState) -> dict[str, Any]:
        """Python-side gap computation - see :func:`_compute_hard_gaps`."""
        hard_gaps = _compute_hard_gaps(
            state.get("user_skill_levels") or {}, state.get("market_skill_stats") or []
        )
        return {"hard_gaps": hard_gaps}

    async def build_result(self, state: SkillAnalysisState) -> dict[str, Any]:
        """Assemble the final response - see :func:`build_gap_analysis_result`."""
        result = build_gap_analysis_result(
            state.get("hard_gaps") or [],
            state.get("user_skills") or [],
            state.get("market_skill_stats") or [],
        )
        result["target_role_ready"] = bool(state.get("target_role_ready", True))
        result["target_role_title"] = state.get("target_role_title")
        result["sample_status"] = state.get("sample_status")
        result["sample_job_count"] = int(state.get("sample_job_count") or 0)
        return {"analysis_result": result}

    async def run(
        self, user_id: str, target_role_id: str | None = None
    ) -> dict[str, Any]:
        """Run the pipeline.

        Args:
            user_id: Person to analyze.
            target_role_id: When given, runs the gap analysis against this
                specific :class:`TargetRole`'s sampled-postings demand
                instead of the aggregate market demand across career offers.

        """
        initial_state: SkillAnalysisState = {
            "user_id": user_id,
            "target_role_id": target_role_id,
            "target_role_title": None,
            "target_role_ready": True,
            "sample_status": None,
            "sample_job_count": 0,
            "user_skills": [],
            "user_skill_levels": {},
            "market_skill_stats": [],
            "hard_gaps": [],
            "analysis_result": {},
        }

        final_state: SkillAnalysisState = await self.graph.ainvoke(initial_state)
        return dict(final_state["analysis_result"])

    async def suggest_projects_for_skills(
        self,
        user_id: str,
        skills: list[str],
    ) -> list[dict[str, Any]]:
        """Generate portfolio project briefs for an explicit skill list."""
        target_skills = [str(s).strip() for s in skills if str(s).strip()]
        if len(target_skills) < 2:
            raise ValueError("At least 2 skills are required to suggest projects")

        user_rows = await self.kg_repository.get_person_skills(user_id)
        user_skills = [str(s.get("name") or "") for s in user_rows if s.get("name")]
        context = await self.graph_rag.assemble_context(
            f"Skills and experience for user {user_id}",
            top_k=8,
            person_id=user_id,
            label_preset="skill_gap",
        )

        chain = SUGGESTED_PROJECTS_PROMPT | self.llm | RobustJsonOutputParser()
        try:
            raw_result = await chain.ainvoke(
                {
                    "user_skills": ", ".join(user_skills) or "None listed",
                    "target_skills": ", ".join(target_skills),
                    "context": context or "No additional context available.",
                }
            )
        except Exception as exc:
            logger.warning(
                "Suggested-projects JSON parse failed, using heuristic fallback: %s",
                exc,
            )
            raw_result = {
                "suggested_projects": _fallback_suggested_projects(target_skills)
            }

        normalized = normalize_skill_analysis(
            {
                "suggested_projects": (
                    raw_result.get("suggested_projects", [])
                    if isinstance(raw_result, dict)
                    else []
                ),
            }
        )
        return list(normalized.get("suggested_projects") or [])


def _format_included_projects(projects: list[dict[str, Any]]) -> str:
    """Render the projects the user chose to include in the roadmap."""
    if not projects:
        return ""
    lines = []
    for project in projects:
        title = str(project.get("title") or "").strip()
        if not title:
            continue
        skills = [str(s) for s in (project.get("skills_covered") or []) if s]
        line = f"- {title}"
        if skills:
            line += f" (covers: {', '.join(skills)})"
        lines.append(line)
    return "\n".join(lines)


def normalize_learning_roadmap(result: dict[str, Any]) -> dict[str, Any]:
    """Coerce LLM output into the roadmap shape expected by the frontend."""
    if not isinstance(result, dict):
        result = {}

    phases: list[dict[str, Any]] = []
    for phase in result.get("phases", []):
        if not isinstance(phase, dict):
            continue
        title = str(phase.get("title", "")).strip()
        if not title:
            continue
        concepts = [
            str(c).strip() for c in (phase.get("concepts") or []) if str(c).strip()
        ]
        steps = [str(s).strip() for s in (phase.get("steps") or []) if str(s).strip()]
        project_title = phase.get("project_title") or phase.get("linked_project")
        phases.append(
            {
                "title": title,
                "duration": str(phase.get("duration", "")).strip(),
                "goal": str(phase.get("goal", "")).strip(),
                "concepts": concepts,
                "steps": steps,
                "project_title": str(project_title).strip() if project_title else None,
            }
        )

    return {
        "overview": str(result.get("overview", "")).strip(),
        "overall_duration": str(result.get("overall_duration", "")).strip(),
        "phases": phases,
    }


def _fallback_roadmap(
    target_skills: list[str], included_projects: list[dict[str, Any]]
) -> dict[str, Any]:
    """Deterministic roadmap when the LLM call/parse fails: one phase per
    ~4 skills, with the first included project scheduled onto the final
    phase.
    """
    phases: list[dict[str, Any]] = []
    chunk_size = max(1, -(-len(target_skills) // 4)) if target_skills else 1
    for index in range(0, len(target_skills), chunk_size):
        chunk = target_skills[index : index + chunk_size]
        if not chunk:
            continue
        phases.append(
            {
                "title": f"Phase {len(phases) + 1}: {', '.join(chunk)}",
                "duration": "1-2 weeks",
                "goal": f"Build working proficiency in {', '.join(chunk)}.",
                "concepts": chunk,
                "steps": [f"Study the fundamentals of {skill}" for skill in chunk]
                + [f"Practice {chunk[0]} with a small hands-on exercise"],
                "project_title": None,
            }
        )
        if len(phases) >= 4:
            break

    if phases and included_projects:
        first_title = str(included_projects[0].get("title") or "").strip()
        phases[-1]["project_title"] = first_title or None

    skills_label = ", ".join(target_skills) or "the selected skills"
    return {
        "overview": f"Focused roadmap covering {skills_label}.",
        "overall_duration": f"{max(1, len(phases)) * 2} weeks (approx.)",
        "phases": phases,
    }


class LearningRoadmapPipeline:
    """Generates a phased learning roadmap (LLM) for an explicit set of
    skills the user chose to work on - unified across gaps, market-demand
    picks, and typed skills on the Skills page - optionally scheduling one
    or more already-chosen Suggested Projects into the phases that need
    them. Deliberately separate from :class:`SkillAnalysisPipeline`: gaps
    are free/instant, a roadmap is an explicit, occasional LLM generation.
    """

    def __init__(
        self,
        kg_repository: KGRepository,
        graph_rag: GraphRAG,
        kg_ingestion: KGIngestion | None = None,
    ) -> None:
        self.kg_repository = kg_repository
        self.graph_rag = graph_rag
        self.kg_ingestion = kg_ingestion or KGIngestion(
            kg_repository=kg_repository,
            embeddings=KGEmbeddings(kg_repository=kg_repository),
            scrape_ttl_days=settings.job_scrape_ttl_days,
        )
        self.llm = get_chat_llm(temperature=0.2, max_tokens=4000)

    async def generate(
        self,
        user_id: str,
        skills: list[str],
        target_role_id: str | None = None,
        included_projects: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        target_skills = [str(s).strip() for s in skills if str(s).strip()]
        if not target_skills:
            raise ValueError("At least one skill is required to generate a roadmap")
        projects = included_projects or []

        try:
            brief = await self.kg_repository.get_person_career_brief(user_id)
        except Exception as exc:
            logger.warning("Failed to load person context for roadmap: %s", exc)
            brief = {}
        person_context = _format_person_brief(brief)

        market_label = "current market demand"
        role_context = ""
        if target_role_id:
            role_rows = await self.kg_repository.query(
                "MATCH (t:TargetRole {id: $id}) RETURN t.title AS title",
                {"id": target_role_id},
            )
            title = role_rows[0].get("title") if role_rows else None
            if title:
                market_label = f"the target role '{title}'"
                try:
                    job_ids = await self.kg_repository.get_target_role_sample_job_ids(
                        target_role_id
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to load role sample ids for roadmap: %s", exc
                    )
                    job_ids = []
                if job_ids:
                    try:
                        hits = await self.graph_rag.retrieve_scoped(
                            str(title), node_ids=job_ids, top_k=_MAX_ROLE_POSTING_HITS
                        )
                        role_context = _format_role_postings(hits)
                    except Exception as exc:
                        logger.warning(
                            "GraphRAG scoped retrieve failed for roadmap: %s", exc
                        )

        chain = LEARNING_ROADMAP_PROMPT | self.llm | RobustJsonOutputParser()
        try:
            raw_result = await chain.ainvoke(
                {
                    "target_skills": ", ".join(target_skills),
                    "market_label": market_label,
                    "role_context": role_context or "No specific postings retrieved.",
                    "included_projects": _format_included_projects(projects)
                    or "None selected.",
                    "context": person_context,
                }
            )
        except Exception as exc:
            logger.warning(
                "Learning roadmap JSON parse failed, using heuristic fallback: %s", exc
            )
            raw_result = _fallback_roadmap(target_skills, projects)

        roadmap = normalize_learning_roadmap(raw_result)
        await self._persist_roadmap(user_id, roadmap)
        return roadmap

    async def _persist_roadmap(self, user_id: str, roadmap: dict[str, Any]) -> None:
        """Write each phase to the KG as a durable LearningResource so
        Career/the KG still have something queryable, per the redesign plan.
        """
        for phase in roadmap.get("phases", []):
            try:
                await self.kg_ingestion.ingest_learning_resource(
                    title=str(phase.get("title", "Learning phase")),
                    url="",
                    resource_type="course",
                    skill_name=str((phase.get("concepts") or [""])[0]),
                    description=str(phase.get("goal", "")),
                    person_id=user_id,
                )
            except Exception as exc:
                logger.warning("Failed to persist roadmap phase: %s", exc)
