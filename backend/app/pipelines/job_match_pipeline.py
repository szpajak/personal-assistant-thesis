"""Pipeline for matching job offers against user skills via LLM."""

from __future__ import annotations

import asyncio
import logging
import math
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from ..db.job_listing_repository import JobListingRepository, listing_to_dict
from ..kg.chains import get_chat_llm
from ..kg.embeddings import KGEmbeddings
from ..kg.graphrag import GraphRAG
from ..kg.repository import KGRepository
from ..prompts.job_prompts import JOB_MATCHING_PROMPT
from ..utils.llm_json import RobustJsonOutputParser
from ..utils.skill_ids import canonicalize_skill_list
from ..utils.skill_extract import seed_required_skills
from ..utils.skill_match import compute_skill_match


logger = logging.getLogger(__name__)

# DeepSeek Flash has no published tokens-per-minute cap (just a 2500
# concurrent-request account ceiling), so this only needs to bound how many
# requests we personally fan out at once, not survive a tiny free-tier TPM
# budget.
_MATCH_CONCURRENCY = 20
# Real scraped LinkedIn/Indeed postings run roughly 2000-5000 characters once
# responsibilities + requirements + benefits + company blurb are included;
# 6000 keeps the large majority intact while still bounding pathological
# scrapes (duplicated boilerplate, stray whitespace runs).
_DESCRIPTION_MAX_CHARS = 6000
# The candidate's entire real career (roles/projects/certificates/education)
# - the point of grounding the LLM in explicit graph evidence instead of a
# vector search is defeated if it gets truncated back down to a stub. 12000
# chars (~3000 tokens) is still under 3% of the model's 1M-token window.
_CONTEXT_MAX_CHARS = 12000
# Job matching cares about the candidate's own portfolio (Project/Skill/
# Certificate), never other JobOffers - those would just be noise for
# "does this person fit this role", unlike the CV pipeline this mirrors.
_MATCH_RETRIEVAL_LABELS = ["Project", "Skill", "Certificate"]
# Evidence chains are per required skill and each already yields a few
# sentences; 8 keeps the prompt focused on the role's actual core skills
# instead of every minor keyword on the listing.
_MATCH_EVIDENCE_SKILL_CAP = 8
# Lucene (and MiniLM) choke on a full scraped job description. Retrieval
# only needs the title, required skills, and a short snippet.
_RETRIEVAL_SNIPPET_CHARS = 400


class JobMatchState(TypedDict):
    """State for the job matching pipeline."""

    user_id: str
    job_ids: list[str]
    use_llm: bool
    shortlist_top_k: int | None
    user_skills: list[dict[str, str]]
    job_offers: list[dict[str, Any]]
    matches: list[dict[str, Any]]


def _merge_job_skills(job: dict[str, Any], linked_skills: list[str] | None) -> list[str]:
    """Combine the JobOffer.required_skills property with REQUIRES edge names."""
    from_property = job.get("required_skills") or []
    if isinstance(from_property, str):
        from_property = [from_property]
    if not isinstance(from_property, list):
        from_property = []

    combined = [
        str(skill).strip()
        for skill in list(from_property) + list(linked_skills or [])
        if isinstance(skill, str) and skill.strip()
    ]
    return canonicalize_skill_list(combined)


def _format_user_skills(skills: list[dict[str, str]]) -> str:
    if not skills:
        return "None listed"
    return ", ".join(
        f"{skill['name']} ({skill.get('level') or 'intermediate'})" for skill in skills
    )


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _format_candidate_profile(brief: dict[str, Any], max_chars: int = _CONTEXT_MAX_CHARS) -> str:
    """Render the person's own career subgraph as a compact briefing.

    Unlike the old GraphRAG ``experience_context`` (a job-independent hybrid
    search over the candidate's own skill names), this is a direct,
    deterministic read of real roles/projects/certificates/education from
    :meth:`KGRepository.get_person_career_brief` - grounding the LLM's
    justification in actual evidence rather than vector similarity.
    """
    parts: list[str] = []

    employment = sorted(
        brief.get("employment") or [],
        key=lambda e: str(e.get("start_date") or ""),
        reverse=True,
    )
    if employment:
        parts.append("ROLES:")
        for emp in employment:
            period = f"{emp.get('start_date') or '?'}\u2013{emp.get('end_date') or 'present'}"
            skills = ", ".join(str(s) for s in (emp.get("skills") or []) if s)
            desc = _truncate(str(emp.get("description") or ""), 600)
            parts.append(f"- {emp.get('title') or ''} at {emp.get('company') or ''} ({period})")
            if skills:
                parts.append(f"  skills: {skills}")
            if desc:
                parts.append(f"  {desc}")

    projects = sorted(
        brief.get("projects") or [],
        key=lambda p: str(p.get("start_date") or ""),
        reverse=True,
    )[:10]
    if projects:
        parts.append("PROJECTS:")
        for proj in projects:
            skills = ", ".join(str(s) for s in (proj.get("skills") or []) if s)
            desc = _truncate(str(proj.get("description") or ""), 600)
            seniority = f", {proj.get('seniority')}" if proj.get("seniority") else ""
            parts.append(f"- {proj.get('title') or ''}{seniority}")
            if skills:
                parts.append(f"  used: {skills}")
            if desc:
                parts.append(f"  {desc}")

    certificates = brief.get("certificates") or []
    if certificates:
        parts.append("CERTIFICATES:")
        for cert in certificates:
            skills = ", ".join(str(s) for s in (cert.get("skills") or []) if s)
            line = f"- {cert.get('title') or ''} ({cert.get('issuer') or 'unknown issuer'})"
            if skills:
                line += f" \u2014 validates: {skills}"
            parts.append(line)

    education = brief.get("education") or []
    if education:
        parts.append("EDUCATION:")
        for edu in education:
            parts.append(
                f"- {edu.get('degree') or ''} in {edu.get('field_of_study') or ''}, "
                f"{edu.get('institution') or ''}"
            )

    text = "\n".join(parts).strip()
    if not text:
        return "No roles, projects, certificates, or education recorded."
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "…"
    return text


def _format_retrieval_hits(
    hits: list[dict[str, Any]], max_chars: int = _CONTEXT_MAX_CHARS
) -> str:
    """Render :meth:`GraphRAG.retrieve` hits as a compact evidence excerpt.

    Unlike :meth:`_format_candidate_profile` (a full career dump), this only
    covers the handful of projects/skills/certificates the hybrid search
    judged most relevant to *this* job - the point of per-job retrieval.
    """
    if not hits:
        return ""

    parts = ["RELEVANT CANDIDATE EVIDENCE (retrieved from knowledge graph for this job):"]
    for hit in hits:
        node = hit.get("node") or {}
        label = hit.get("label", "Unknown")
        title = node.get("title") or node.get("name") or "Untitled"
        desc = _truncate(str(node.get("description") or ""), 300)
        line = f"- [{label}] {title}"
        if desc:
            line += f": {desc}"
        parts.append(line)
        for rel in hit.get("related") or []:
            rel_node = rel.get("node") or {}
            rel_name = rel_node.get("title") or rel_node.get("name") or ""
            rel_type = rel.get("relationship_type", "RELATED_TO")
            if rel_name:
                parts.append(f"    connected via {rel_type}: {rel_name}")

    text = "\n".join(parts)
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "…"
    return text


def _format_job_skills(job_skills: list[str], skill_levels: dict[str, str]) -> str:
    """Render required skills with their ``REQUIRES.level`` when known."""
    if not job_skills:
        return "Not listed"
    parts = []
    for name in job_skills:
        level = skill_levels.get(str(name).strip().lower())
        parts.append(f"{name} ({level})" if level else str(name))
    return ", ".join(parts)


def _clamp_score(value: Any) -> int:
    try:
        score = int(round(float(value)))
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, score))


def _as_skill_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _job_retrieval_query(job: dict[str, Any]) -> str:
    """Compact lexical/vector query: title + skills + a short description snippet.

    A full scraped job description is thousands of Lucene clauses
    (``TooManyClauses``) and MiniLM truncates it anyway.
    """
    title = str(job.get("title") or "").strip()
    skills = [
        str(s).strip()
        for s in (job.get("required_skills") or [])
        if str(s).strip()
    ]
    snippet = str(job.get("description") or "")[:_RETRIEVAL_SNIPPET_CHARS].strip()
    parts = [title]
    if skills:
        parts.append(", ".join(skills[:_MATCH_EVIDENCE_SKILL_CAP]))
    if snippet:
        parts.append(snippet)
    return "\n".join(part for part in parts if part).strip() or title


class JobMatchPipeline:
    """Match jobs to a candidate using an LLM that weighs skill levels."""

    def __init__(
        self,
        kg_repository: KGRepository,
        job_listing_repository: JobListingRepository | None = None,
        embeddings: KGEmbeddings | None = None,
        graph_rag: GraphRAG | None = None,
    ) -> None:
        self.kg_repository = kg_repository
        self.job_listing_repository = job_listing_repository
        self.embeddings = embeddings or KGEmbeddings(kg_repository=kg_repository)
        self.graph_rag = graph_rag or GraphRAG(
            kg_repository=kg_repository, embeddings=self.embeddings
        )
        # Short JSON score+justification per job. 1500 leaves room if
        # thinking-disable is ignored by a provider change; 600 was enough
        # to let a reasoning trace consume the whole budget and return empty.
        self.llm = get_chat_llm(temperature=0, max_tokens=1500)
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        """Build the LangGraph StateGraph."""
        workflow = StateGraph(JobMatchState)

        workflow.add_node("fetch_user_skills", self.fetch_user_skills)
        workflow.add_node("fetch_job_offers", self.fetch_job_offers)
        workflow.add_node("match_each_job", self.match_each_job)

        workflow.set_entry_point("fetch_user_skills")
        workflow.add_edge("fetch_user_skills", "fetch_job_offers")
        workflow.add_edge("fetch_job_offers", "match_each_job")
        workflow.add_edge("match_each_job", END)

        return workflow.compile()

    async def _known_skill_names(self) -> list[str]:
        try:
            return await self.kg_repository.list_skill_names()
        except Exception as exc:
            logger.warning("Failed to load known skill names for heuristic extraction: %s", exc)
            return []

    async def fetch_user_skills(self, state: JobMatchState) -> dict[str, Any]:
        """Fetch direct + project-derived skills (with proficiency levels)."""
        user_id = state["user_id"]
        skills = await self.kg_repository.get_person_skills(user_id)
        user_skills: list[dict[str, str]] = []
        seen: set[str] = set()
        for skill in skills:
            name = str(skill.get("name", "")).strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            user_skills.append(
                {
                    "name": name,
                    "level": str(skill.get("level") or "intermediate").strip().lower(),
                }
            )
        return {"user_skills": user_skills}

    async def _build_job_evidence(self, job: dict[str, Any], person_id: str) -> str:
        """Per-job GraphRAG evidence excerpt, replacing the old one-shot
        batch career brief (see module docstring / plan section 3): each
        LLM-scored job gets its own retrieval over the candidate's
        Project/Skill/Certificate subgraph, biased toward that specific
        job's title+description, plus evidence chains for its top required
        skills. Falls back to the full career brief when retrieval finds
        nothing (e.g. an early, still-sparse KG).
        """
        title = str(job.get("title") or "")
        query = _job_retrieval_query(job)

        hits: list[dict[str, Any]] = []
        try:
            hits = await self.graph_rag.retrieve(
                query,
                top_k=8,
                hops=1,
                person_id=person_id,
                label_preset="job_match",
                labels=_MATCH_RETRIEVAL_LABELS,
            )
        except Exception as exc:
            logger.warning(
                "GraphRAG retrieve failed for job %s (%s); falling back to career brief: %s",
                job.get("id"),
                title,
                exc,
            )

        if not hits:
            try:
                brief = await self.kg_repository.get_person_career_brief(person_id)
            except Exception as exc:
                logger.warning("Failed to load candidate career brief: %s", exc)
                brief = {}
            return _format_candidate_profile(brief)

        evidence_parts = [_format_retrieval_hits(hits)]
        required_skills = [
            str(s) for s in (job.get("required_skills") or []) if str(s).strip()
        ][:_MATCH_EVIDENCE_SKILL_CAP]
        for skill_name in required_skills:
            try:
                chain_text = await self.graph_rag.assemble_evidence_chain(
                    person_id=person_id, skill_name=skill_name
                )
            except Exception as exc:
                logger.debug(
                    "Evidence chain failed for skill %s on job %s: %s",
                    skill_name,
                    job.get("id"),
                    exc,
                )
                continue
            evidence_parts.append(chain_text)

        text = "\n\n".join(part for part in evidence_parts if part)
        if len(text) > _CONTEXT_MAX_CHARS:
            return text[:_CONTEXT_MAX_CHARS].rstrip() + "…"
        return text

    async def fetch_job_offers(self, state: JobMatchState) -> dict[str, Any]:
        """Fetch only the requested job ids from Neo4j and/or Postgres."""
        job_ids = [str(jid) for jid in (state.get("job_ids") or []) if str(jid).strip()]
        if not job_ids:
            return {"job_offers": []}

        job_offers: list[dict[str, Any]] = []
        remaining = set(job_ids)

        offers = await self.kg_repository.query(
            """
            MATCH (j:JobOffer)
            WHERE j.id IN $job_ids
            OPTIONAL MATCH (j)-[r:REQUIRES]->(s:Skill)
            WITH j,
                 collect(DISTINCT s.name) AS linked_skills,
                 collect(DISTINCT CASE WHEN s IS NULL THEN NULL ELSE {name: s.name, level: r.level} END) AS requires_raw
            RETURN properties(j) AS job, linked_skills,
                   [x IN requires_raw WHERE x IS NOT NULL] AS requires_levels
            """,
            {"job_ids": job_ids},
        )
        for row in offers:
            job = dict(row.get("job") or {})
            job_id = str(job.get("id") or "")
            if not job_id:
                continue
            job["required_skills"] = _merge_job_skills(
                job, row.get("linked_skills") or []
            )
            job["skill_levels"] = {
                str(entry.get("name")).strip().lower(): entry.get("level")
                for entry in (row.get("requires_levels") or [])
                if entry.get("name") and entry.get("level")
            }
            job["tier"] = "career"
            job_offers.append(job)
            remaining.discard(job_id)

        if remaining and self.job_listing_repository is not None:
            known_names = await self._known_skill_names()
            for listing_id in list(remaining):
                listing = await self.job_listing_repository.get_by_id(listing_id)
                if not listing:
                    continue
                data = listing_to_dict(listing)
                data["required_skills"] = seed_required_skills(
                    data.get("required_skills"),
                    f"{data.get('title') or ''}\n{data.get('description') or ''}".strip(),
                    known_names,
                )
                data["tier"] = "staging"
                job_offers.append(data)
                remaining.discard(listing_id)

        # Preserve caller order where possible.
        by_id = {str(j.get("id")): j for j in job_offers}
        ordered = [by_id[jid] for jid in job_ids if jid in by_id]
        return {"job_offers": ordered}

    async def match_each_job(self, state: JobMatchState) -> dict[str, Any]:
        """Score jobs: always compute overlap; optionally LLM-score a shortlist."""
        user_id = state["user_id"]
        user_skills = state["user_skills"]
        user_skill_names = [skill["name"] for skill in user_skills]
        use_llm = bool(state.get("use_llm", True))
        shortlist_top_k = state.get("shortlist_top_k")

        scored: list[dict[str, Any]] = []
        for job in state["job_offers"]:
            job_skills = job.get("required_skills") or []
            if not isinstance(job_skills, list):
                job_skills = []
            overlap = compute_skill_match(
                user_skill_names,
                [str(skill) for skill in job_skills],
            )
            scored.append(
                {
                    "job": job,
                    "quick_score": overlap.match_score,
                    "matching_skills": overlap.matching_skills,
                    "missing_skills": overlap.missing_skills,
                    "required_skills": job_skills,
                }
            )

        llm_targets = scored
        if use_llm and shortlist_top_k is not None and len(scored) > shortlist_top_k:
            llm_targets = await self._shortlist(scored, user_skills, shortlist_top_k)
        elif not use_llm:
            llm_targets = []

        llm_ids = {str(item["job"].get("id")) for item in llm_targets}
        semaphore = asyncio.Semaphore(_MATCH_CONCURRENCY)

        async def _score_llm(item: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                return await self._match_single_job(
                    item["job"],
                    user_skills,
                    user_id,
                    quick_score=item["quick_score"],
                )

        llm_results: dict[str, dict[str, Any]] = {}
        if llm_targets:
            results = await asyncio.gather(*[_score_llm(item) for item in llm_targets])
            for res in results:
                llm_results[str(res.get("job_id"))] = res

        matches: list[dict[str, Any]] = []
        for item in scored:
            job = item["job"]
            job_id = str(job.get("id") or "")
            if job_id in llm_results:
                matches.append(llm_results[job_id])
                continue
            matches.append(
                {
                    "job_id": job_id,
                    "job_title": job.get("title", ""),
                    "company": job.get("company"),
                    "match_score": item["quick_score"],
                    "quick_score": item["quick_score"],
                    "matching_skills": item["matching_skills"],
                    "missing_skills": item["missing_skills"],
                    "required_skills": item["required_skills"],
                    "justification": "Quick skill-overlap score (LLM not run).",
                    "source": "overlap",
                    "tier": job.get("tier") or "staging",
                }
            )

        ranked = sorted(
            matches, key=lambda entry: entry.get("match_score", 0), reverse=True
        )
        return {"matches": ranked}

    async def _shortlist(
        self,
        scored: list[dict[str, Any]],
        user_skills: list[dict[str, str]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Rank by overlap, then local embedding similarity; keep top_k for LLM."""
        skill_blob = ", ".join(
            f"{s['name']} ({s.get('level') or 'intermediate'})" for s in user_skills
        ) or "candidate skills"
        try:
            user_vec = await self.embeddings.embed_text(skill_blob)
        except Exception as exc:
            logger.warning("Embedding shortlist failed; using overlap only: %s", exc)
            return sorted(
                scored, key=lambda item: item["quick_score"], reverse=True
            )[:top_k]

        ranked: list[tuple[float, dict[str, Any]]] = []
        for item in scored:
            job = item["job"]
            job_text = (
                f"{job.get('title') or ''} at {job.get('company') or ''}. "
                f"Skills: {', '.join(str(s) for s in (item['required_skills'] or []))}. "
                # The local MiniLM encoder self-truncates at ~256 tokens
                # (~1000 chars), so slicing shorter than that just throws
                # away content the encoder could still use.
                f"{str(job.get('description') or '')[:1000]}"
            )
            try:
                job_vec = await self.embeddings.embed_text(job_text)
                sim = _cosine(user_vec, job_vec)
            except Exception:
                sim = 0.0
            # Blend overlap (0-100) with cosine similarity.
            rank_score = (0.7 * item["quick_score"]) + (30.0 * sim)
            ranked.append((rank_score, item))

        ranked.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in ranked[:top_k]]

    async def _match_single_job(
        self,
        job: dict[str, Any],
        user_skills: list[dict[str, str]],
        person_id: str,
        quick_score: int,
    ) -> dict[str, Any]:
        job_skills = job.get("required_skills") or []
        if not isinstance(job_skills, list):
            job_skills = []

        description = str(job.get("description") or "")
        # Always include a (truncated) description alongside structured skills:
        # skills alone miss years of experience, domain, language, on-site/remote, etc.
        if len(description) > _DESCRIPTION_MAX_CHARS:
            description_for_prompt = description[:_DESCRIPTION_MAX_CHARS] + "…"
        else:
            description_for_prompt = description or "No description provided."

        try:
            context = await self._build_job_evidence(job, person_id)
            chain = JOB_MATCHING_PROMPT | self.llm | RobustJsonOutputParser()
            result = await chain.ainvoke(
                {
                    "job_title": job.get("title") or "",
                    "job_company": job.get("company") or "",
                    "job_skills": _format_job_skills(
                        [str(s) for s in job_skills], job.get("skill_levels") or {}
                    ),
                    "job_description": description_for_prompt,
                    "user_skills": _format_user_skills(user_skills),
                    "context": context or "No additional context available.",
                }
            )
            return {
                "job_id": job.get("id"),
                "job_title": job.get("title", ""),
                "company": job.get("company"),
                "match_score": _clamp_score(result.get("match_score")),
                "quick_score": quick_score,
                "matching_skills": _as_skill_list(result.get("matching_skills")),
                "missing_skills": _as_skill_list(result.get("missing_skills")),
                "required_skills": job_skills,
                "justification": str(result.get("justification") or "").strip(),
                "source": "llm",
                "tier": job.get("tier") or "staging",
            }
        except Exception as exc:
            logger.warning(
                "LLM job match failed for %s (%s); falling back to skill overlap: %s",
                job.get("id"),
                job.get("title"),
                exc,
            )
            fallback = compute_skill_match(
                [skill["name"] for skill in user_skills],
                [str(skill) for skill in job_skills],
            )
            return {
                "job_id": job.get("id"),
                "job_title": job.get("title", ""),
                "company": job.get("company"),
                "match_score": fallback.match_score,
                "quick_score": quick_score,
                "matching_skills": fallback.matching_skills,
                "missing_skills": fallback.missing_skills,
                "required_skills": job_skills,
                "justification": "Fallback overlap score (LLM unavailable).",
                "source": "overlap",
                "tier": job.get("tier") or "staging",
            }

    async def run(
        self,
        user_id: str,
        job_ids: list[str] | None = None,
        *,
        use_llm: bool = True,
        shortlist_top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Run the pipeline for an explicit set of job ids."""
        initial_state: JobMatchState = {
            "user_id": user_id,
            "job_ids": list(job_ids or []),
            "use_llm": use_llm,
            "shortlist_top_k": shortlist_top_k,
            "user_skills": [],
            "job_offers": [],
            "matches": [],
        }

        final_state: JobMatchState = await self.graph.ainvoke(initial_state)
        return list(final_state["matches"])
