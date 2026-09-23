"""Pipeline for generating personalized CVs for job applications.

GraphRAG here acts as a CURATOR, not just extra context: once a portfolio
has 8-10 projects and 40+ skills, dumping all of it into one CV both runs
out of room and buries what actually matters for a given job offer under
irrelevant detail. So instead of handing the LLM everything and hoping it
picks well, a Python budgeting step (see ``cv_budget.py``) selects a small,
job-relevant subset of projects/skills/certificates from GraphRAG's ranked
hits FIRST, and the single tailoring LLM call is constrained to only ever
mention items from that selection.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from ..kg.chains import get_chat_llm
from ..kg.graphrag import GraphRAG
from ..kg.repository import KGRepository
from ..prompts.cv_prompts import CV_GENERATION_PROMPT
from ..utils.llm_json import RobustJsonOutputParser
from .cv_budget import CVBudget, build_cv_budget

# GraphRAG selection is scoped to the person's own evidence - a job offer is
# never a source of CV content, so it must never be surfaced as a "hit" here.
_CV_RETRIEVAL_LABELS = ["Project", "Skill", "Certificate"]
# How many of the job's required skills get a full evidence-chain lookup
# (Person -> Project/Employment/Certificate). Capped: most postings list
# 10-20+ skills and only the top handful are worth a dedicated evidence trace
# for bullet-writing.
_EVIDENCE_SKILL_CAP = 8


class CVPipelineState(TypedDict):
    """State for the CV generation pipeline."""

    user_id: str
    job_offer_id: str
    job_offer_data: dict[str, Any]
    job_required_skills: list[dict[str, Any]]
    profile: dict[str, Any]
    employment: list[dict[str, Any]]
    education: list[dict[str, Any]]
    all_projects: list[dict[str, Any]]
    all_skills: list[dict[str, Any]]
    all_certificates: list[dict[str, Any]]
    retrieval_hits: list[dict[str, Any]]
    budget: CVBudget
    evidence_text: str
    generated_cv: dict[str, Any]


def _format_employment(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(no employment history recorded)"
    rows = sorted(rows, key=lambda r: str(r.get("start_date") or ""), reverse=True)
    lines = []
    for row in rows:
        period = f"{row.get('start_date', '?')} - {row.get('end_date') or 'present'}"
        lines.append(
            f"- {row.get('title', '')} at {row.get('company', '')} ({period}): "
            f"{row.get('description', '')}"
        )
    return "\n".join(lines)


def _format_selected_projects(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(no projects selected for this job)"
    rows = sorted(rows, key=lambda r: str(r.get("start_date") or ""), reverse=True)
    lines = []
    for row in rows:
        tech = ", ".join(row.get("tech_stack") or [])
        lines.append(
            f"- {row.get('title', '')} [{tech}]: {row.get('description', '')} "
            f"(achievements: {'; '.join(row.get('achievements') or []) or 'none listed'})"
        )
    return "\n".join(lines)


def _format_job_required_skills(skills: list[dict[str, Any]]) -> str:
    if not skills:
        return "Not listed"
    parts = []
    for skill in skills:
        name = str(skill.get("name") or "").strip()
        if not name:
            continue
        level = str(skill.get("level") or "").strip()
        parts.append(f"{name} ({level})" if level else name)
    return ", ".join(parts) or "Not listed"


class CVPipeline:
    """Handles the CV generation process using LangGraph."""

    def __init__(self, kg_repository: KGRepository, graph_rag: GraphRAG) -> None:
        self.kg_repository = kg_repository
        self.graph_rag = graph_rag
        # Tailored JSON (headline + summary + skill groups + per-role/project
        # bullets) needs more headroom than a short classification response.
        self.llm = get_chat_llm(temperature=0, max_tokens=4000)
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        """Build the LangGraph StateGraph."""
        workflow = StateGraph(CVPipelineState)

        workflow.add_node("fetch_job_offer", self.fetch_job_offer)
        workflow.add_node("fetch_static_profile", self.fetch_static_profile)
        workflow.add_node("graphrag_select", self.graphrag_select)
        workflow.add_node("build_budget", self.build_budget)
        workflow.add_node("generate_cv_section", self.generate_cv_section)

        workflow.set_entry_point("fetch_job_offer")
        workflow.add_edge("fetch_job_offer", "fetch_static_profile")
        workflow.add_edge("fetch_static_profile", "graphrag_select")
        workflow.add_edge("graphrag_select", "build_budget")
        workflow.add_edge("build_budget", "generate_cv_section")
        workflow.add_edge("generate_cv_section", END)

        return workflow.compile()

    async def fetch_job_offer(self, state: CVPipelineState) -> dict[str, Any]:
        """Fetch the job offer and its REQUIRES skills (with level/importance
        now written by ``KGIngestion.promote_job``'s LLM analysis).
        """
        job_offer_id = state["job_offer_id"]
        job_node = await self.kg_repository.get_node("JobOffer", job_offer_id)
        rows = await self.kg_repository.query(
            """
            MATCH (j:JobOffer {id: $job_id})-[r:REQUIRES]->(s:Skill)
            RETURN s.name AS name, r.level AS level, r.importance AS importance
            """,
            {"job_id": job_offer_id},
        )
        required_skills = [
            {"name": row.get("name"), "level": row.get("level"), "importance": row.get("importance")}
            for row in rows
            if row.get("name")
        ]
        return {"job_offer_data": job_node or {}, "job_required_skills": required_skills}

    async def fetch_static_profile(self, state: CVPipelineState) -> dict[str, Any]:
        """Fetch profile/chronology facts that are the same for every CV
        (headers, employment, education) plus the FULL project/skill/
        certificate universe the budget step selects from - none of this
        goes into the prompt unfiltered.
        """
        user_id = state["user_id"]
        profile = await self.kg_repository.get_node("Person", user_id)
        employment = await self.kg_repository.find_related_nodes(
            "Person", user_id, relationship_type="WORKED_AT"
        )
        education = await self.kg_repository.find_related_nodes(
            "Person", user_id, relationship_type="STUDIED_AT"
        )
        projects = await self.kg_repository.find_related_nodes(
            "Person", user_id, relationship_type="PRODUCED"
        )
        skills = await self.kg_repository.get_person_skills(user_id)

        cert_rows = await self.kg_repository.query(
            """
            MATCH (p:Person {id: $person_id})-[:HAS_CERTIFICATE]->(c:Certificate)
            OPTIONAL MATCH (c)-[:VALIDATES]->(s:Skill)
            WITH c, collect(DISTINCT s.name) AS validated_skills
            RETURN properties(c) AS cert, validated_skills
            """,
            {"person_id": user_id},
        )
        certificates = [
            {**dict(row.get("cert") or {}), "validated_skills": row.get("validated_skills") or []}
            for row in cert_rows
        ]

        return {
            "profile": profile or {},
            "employment": employment,
            "education": education,
            "all_projects": projects,
            "all_skills": skills,
            "all_certificates": certificates,
        }

    async def graphrag_select(self, state: CVPipelineState) -> dict[str, Any]:
        """Retrieve ranked Project/Skill/Certificate hits for this job offer,
        scoped to this person - the "cv" label preset - EXCLUDING JobOffer
        entirely (a job posting is never CV evidence about the candidate).
        """
        job_title = state["job_offer_data"].get("title", "")
        job_desc = state["job_offer_data"].get("description", "")
        query = f"Job title: {job_title}\nDescription: {job_desc}"

        hits = await self.graph_rag.retrieve(
            query,
            top_k=8,
            hops=1,
            person_id=state["user_id"],
            label_preset="cv",
            labels=_CV_RETRIEVAL_LABELS,
        )
        return {"retrieval_hits": hits}

    async def build_budget(self, state: CVPipelineState) -> dict[str, Any]:
        """Python-side selection (see ``cv_budget.build_cv_budget``) of a
        small, job-relevant subset of projects/skills/certificates, plus an
        evidence chain for the job's top required skills to ground bullets.
        """
        budget = build_cv_budget(
            retrieval_hits=state["retrieval_hits"],
            all_projects=state["all_projects"],
            all_skills=state["all_skills"],
            all_certificates=state["all_certificates"],
            job_required_skills=state["job_required_skills"],
        )

        evidence_skills = [
            str(s.get("name") or "").strip()
            for s in state["job_required_skills"][:_EVIDENCE_SKILL_CAP]
            if str(s.get("name") or "").strip()
        ]
        evidence_chunks = []
        for skill_name in evidence_skills:
            try:
                chunk = await self.graph_rag.assemble_evidence_chain(
                    person_id=state["user_id"], skill_name=skill_name
                )
            except Exception:
                continue
            evidence_chunks.append(chunk)

        return {"budget": budget, "evidence_text": "\n".join(evidence_chunks)}

    async def generate_cv_section(self, state: CVPipelineState) -> dict[str, Any]:
        """Ask the LLM only for content that genuinely needs per-job tailoring:
        headline, summary, skill grouping, and bullet points for experience and
        projects - constrained to the Python-selected budget. Contact info,
        education, and certifications/awards are real facts the user already
        curated - they are assembled deterministically by
        ``CVService.format_cv_markdown`` instead of being echoed back
        through the LLM.
        """
        budget: CVBudget = state["budget"]
        chain = CV_GENERATION_PROMPT | self.llm | RobustJsonOutputParser()

        result = await chain.ainvoke(
            {
                "job_offer": state["job_offer_data"],
                "job_required_skills": _format_job_required_skills(state["job_required_skills"]),
                "evidence": state["evidence_text"] or "No additional evidence available.",
                "selected_skills": ", ".join(budget.skills) or "None",
                "employment": _format_employment(state["employment"]),
                "selected_projects": _format_selected_projects(budget.projects),
            }
        )

        return {"generated_cv": result}

    async def run(self, user_id: str, job_offer_id: str) -> dict[str, Any]:
        """Run the pipeline.

        Returns the LLM's tailored JSON (``generated``) alongside the raw
        chronology fetched from the graph (``profile``, ``education``,
        ``certificates``, ``projects``) so the caller can assemble the final
        CV Markdown deterministically. ``projects``/``certificates`` are the
        BUDGET-SELECTED subset (not the person's full portfolio) so
        ``CVService.format_cv_markdown`` only renders what the LLM was
        actually asked to write about.
        """
        initial_state: CVPipelineState = {
            "user_id": user_id,
            "job_offer_id": job_offer_id,
            "job_offer_data": {},
            "job_required_skills": [],
            "profile": {},
            "employment": [],
            "education": [],
            "all_projects": [],
            "all_skills": [],
            "all_certificates": [],
            "retrieval_hits": [],
            "budget": CVBudget(),
            "evidence_text": "",
            "generated_cv": {},
        }

        final_state: CVPipelineState = await self.graph.ainvoke(initial_state)
        budget: CVBudget = final_state["budget"]
        return {
            "generated": dict(final_state["generated_cv"]),
            "profile": final_state.get("profile", {}),
            "education": final_state.get("education", []),
            "certificates": budget.certificates,
            "projects": budget.projects,
        }
