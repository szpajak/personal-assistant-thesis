"""Service for managing and matching job offers."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Literal

from ..config import settings
from ..db.job_listing_repository import JobListingRepository, listing_to_dict
from ..db.job_match_repository import JobMatchRepository
from ..kg.embeddings import KGEmbeddings
from ..kg.ingestion import KGIngestion
from ..kg.repository import KGRepository
from ..pipelines.job_match_pipeline import JobMatchPipeline
from ..schemas.jobs import JobMatchResponse, JobOfferRead, JobPromoteResponse, JobTier
from ..utils.llm_budget import MatchBudgetExceeded, reserve_match_calls
from ..utils.profile_fingerprint import compute_skill_fingerprint
from ..utils.skill_extract import seed_required_skills
from ..utils.skill_ids import canonicalize_skill_list
from ..utils.skill_match import compute_skill_match

logger = logging.getLogger(__name__)


class JobService:
    """Manage scraped (Postgres) listings, career (Neo4j) offers, and matching."""

    def __init__(
        self,
        kg_repository: KGRepository,
        job_match_pipeline: JobMatchPipeline,
        job_listing_repository: JobListingRepository,
        job_match_repository: JobMatchRepository,
        kg_ingestion: KGIngestion | None = None,
    ) -> None:
        self.kg_repository = kg_repository
        self.job_match_pipeline = job_match_pipeline
        self.job_listing_repository = job_listing_repository
        self.job_match_repository = job_match_repository
        self.kg_ingestion = kg_ingestion or KGIngestion(
            kg_repository=kg_repository,
            embeddings=KGEmbeddings(kg_repository=kg_repository),
            scrape_ttl_days=settings.job_scrape_ttl_days,
        )

    async def list_offers(
        self,
        source: str | None = None,
        status: str | None = None,
        search: str | None = None,
        tier: Literal["staging", "career", "all"] | None = "all",
    ) -> list[JobOfferRead]:
        """List scraped (Postgres) listings and/or career (Neo4j) offers."""
        offers: list[JobOfferRead] = []
        if tier in ("career", "all"):
            try:
                offers.extend(await self._list_career_offers(source, status, search))
            except Exception as e:
                logger.error(f"Failed to list career job offers: {e}")
        if tier in ("staging", "all"):
            try:
                offers.extend(
                    await self.list_scraped(source=source, status=status, search=search)
                )
            except Exception as e:
                logger.error(f"Failed to list scraped job listings: {e}")

        offers.sort(key=lambda o: o.scraped_at, reverse=True)
        return offers[:100]

    async def _list_career_offers(
        self,
        source: str | None,
        status: str | None,
        search: str | None,
    ) -> list[JobOfferRead]:
        params: dict[str, object] = {}
        predicates: list[str] = [
            "(job.purpose IS NULL OR job.purpose <> 'market_sample')"
        ]

        if source:
            predicates.append("job.source = $source")
            params["source"] = source
        if status:
            if status == "active":
                predicates.append("(job.status IS NULL OR job.status = 'active')")
            else:
                predicates.append("job.status = $status")
                params["status"] = status
        if search:
            predicates.append(
                "(toLower(job.title) CONTAINS toLower($search) "
                "OR toLower(job.company) CONTAINS toLower($search))"
            )
            params["search"] = search

        where_clause = f"WHERE {' AND '.join(predicates)}" if predicates else ""
        cypher = f"""
        MATCH (job:JobOffer)
        {where_clause}
        OPTIONAL MATCH (job)-[:REQUIRES]->(s:Skill)
        WITH job, collect(DISTINCT s.name) AS linked_skills
        RETURN properties(job) AS job, linked_skills
        ORDER BY job.scraped_at DESC
        LIMIT 100
        """

        results = await self.kg_repository.query(cypher, params)
        offers: list[JobOfferRead] = []
        for row in results:
            job = dict(row.get("job") or {})
            linked = row.get("linked_skills") or []
            props = list(job.get("required_skills") or [])
            if isinstance(props, str):
                props = [props]
            linked_clean = [str(s).strip() for s in linked if str(s).strip()]
            job["required_skills"] = canonicalize_skill_list(
                [str(s).strip() for s in props if str(s).strip()] + linked_clean
            )
            offers.append(self._to_job_read(job, tier="career"))
        return offers

    async def list_scraped(
        self,
        search: str | None = None,
        source: str | None = None,
        status: str | None = "active",
        seniority: str | None = None,
        min_years: int | None = None,
        max_years: int | None = None,
    ) -> list[JobOfferRead]:
        """List scraped-but-not-promoted listings from Postgres."""
        listings = await self.job_listing_repository.list_listings(
            search=search,
            source=source,
            seniority=seniority,
            min_years=min_years,
            max_years=max_years,
            status=status,
        )
        known_names = await self._known_skill_names()
        offers: list[JobOfferRead] = []
        for listing in listings:
            data = listing_to_dict(listing)
            data["required_skills"] = seed_required_skills(
                data.get("required_skills"),
                f"{data.get('title') or ''}\n{data.get('description') or ''}".strip(),
                known_names,
            )
            offers.append(self._to_job_read(data, tier="staging"))
        return offers

    async def list_active_career_job_ids(self) -> list[str]:
        results = await self.kg_repository.query(
            """
            MATCH (j:JobOffer)
            WHERE (j.status IS NULL OR j.status = 'active')
              AND (j.purpose IS NULL OR j.purpose <> 'market_sample')
            RETURN j.id AS id
            ORDER BY j.scraped_at DESC
            LIMIT $limit
            """,
            {"limit": settings.llm_match_batch_max},
        )
        return [str(row["id"]) for row in results if row.get("id")]

    async def delete_scraped(self, listing_id: str) -> bool:
        """Delete a scraped listing (the "reclaim storage" ask)."""
        return await self.job_listing_repository.delete_by_id(listing_id)

    async def promote_job(
        self,
        job_id: str,
        person_id: str,
    ) -> JobPromoteResponse:
        """Promote a scraped listing into the career graph (idempotent)."""
        listing_row = await self.job_listing_repository.get_by_id(job_id)
        listing = listing_to_dict(listing_row) if listing_row else {}

        props, newly_promoted = await self.kg_ingestion.promote_job(
            job_id=job_id,
            listing=listing,
            person_id=person_id,
            extract_skills=True,
        )

        if listing_row:
            await self.job_listing_repository.delete_by_id(job_id)

        return JobPromoteResponse(
            job_offer=self._to_job_read(props, tier="career"),
            promoted=newly_promoted,
        )

    async def list_cached_matches(self, person_id: str) -> list[JobMatchResponse]:
        """Return cached matches + live quick_score for career and staging.

        Never calls the LLM.
        """
        fingerprint = await compute_skill_fingerprint(self.kg_repository, person_id)
        user_skills = await self.kg_repository.get_person_skills(person_id)
        user_skill_names = [
            str(s.get("name") or "").strip()
            for s in user_skills
            if str(s.get("name") or "").strip()
        ]

        career_offers = await self._list_career_offers(None, "active", None)
        try:
            staging_offers = await self.list_scraped(status="active")
        except Exception as exc:
            logger.error("Failed to list scraped listings for overlap scores: %s", exc)
            staging_offers = []
        cached_rows = {
            row.job_id: row
            for row in await self.job_match_repository.list_for_person(person_id)
        }

        matches: list[JobMatchResponse] = []
        for offer in [*career_offers, *staging_offers]:
            matches.append(
                self._overlap_match(
                    offer,
                    user_skill_names,
                    cached_rows.get(offer.id),
                    fingerprint,
                )
            )

        matches.sort(key=lambda m: m.score, reverse=True)
        return matches

    async def match_jobs(
        self,
        person_id: str,
        job_ids: list[str],
        *,
        use_llm: bool = True,
        shortlist_top_k: int | None = None,
    ) -> list[JobMatchResponse]:
        """LLM-match (or overlap-only) an explicit set of job ids and persist."""
        if not job_ids:
            return []

        if use_llm:
            llm_count = len(job_ids)
            if shortlist_top_k is not None:
                llm_count = min(llm_count, shortlist_top_k)
            reserve_match_calls(person_id, llm_count)

        fingerprint = await compute_skill_fingerprint(self.kg_repository, person_id)
        pipeline_results = await self.job_match_pipeline.run(
            user_id=person_id,
            job_ids=job_ids,
            use_llm=use_llm,
            shortlist_top_k=shortlist_top_k,
        )

        matches: list[JobMatchResponse] = []
        for res in pipeline_results:
            job_id = res.get("job_id")
            if not job_id:
                continue
            job_data, tier = await self._resolve_job(str(job_id))
            if not job_data:
                continue

            source = str(res.get("source") or ("llm" if use_llm else "overlap"))
            if source not in {"overlap", "llm"}:
                source = "overlap"
            match_score = int(res.get("match_score") or 0)
            quick_score = int(res.get("quick_score") or match_score)
            matching_skills = list(res.get("matching_skills") or [])
            missing_skills = list(res.get("missing_skills") or [])
            justification = str(res.get("justification") or "")

            await self.job_match_repository.upsert(
                person_id=person_id,
                job_id=str(job_id),
                job_tier=tier or "staging",
                match_score=match_score,
                quick_score=quick_score,
                matching_skills=matching_skills,
                missing_skills=missing_skills,
                justification=justification,
                source=source,
                profile_fingerprint=fingerprint,
            )

            job_offer = self._to_job_read(
                {
                    **job_data,
                    "required_skills": (
                        res.get("required_skills")
                        or job_data.get("required_skills")
                        or []
                    ),
                },
                tier=tier or "staging",
            )
            matches.append(
                JobMatchResponse(
                    job_offer=job_offer,
                    score=float(match_score) / 100.0,
                    matching_skills=matching_skills,
                    missing_skills=missing_skills,
                    justification=justification,
                    quick_score=float(quick_score) / 100.0,
                    is_stale=False,
                    matched_at=datetime.now(UTC),
                    source=source,  # type: ignore[arg-type]
                )
            )

        matches.sort(key=lambda m: m.score, reverse=True)
        return matches

    async def match_single_job(self, person_id: str, job_id: str) -> JobMatchResponse:
        results = await self.match_jobs(
            person_id,
            [job_id],
            use_llm=True,
            shortlist_top_k=None,
        )
        if not results:
            raise ValueError(f"Job {job_id} not found")
        return results[0]

    async def match_batch(
        self,
        person_id: str,
        job_ids: list[str] | None,
    ) -> list[JobMatchResponse]:
        """Empty job_ids → all active career offers (capped); shortlist when large."""
        resolved = [jid for jid in (job_ids or []) if jid and jid.strip()]
        explicit_selection = bool(resolved)
        if not resolved:
            resolved = await self.list_active_career_job_ids()

        resolved = resolved[: settings.llm_match_batch_max]
        shortlist: int | None = None
        if not explicit_selection and len(resolved) > settings.llm_match_batch_top_k:
            shortlist = settings.llm_match_batch_top_k
        elif explicit_selection:
            shortlist = None  # LLM-score every selected id

        return await self.match_jobs(
            person_id,
            resolved,
            use_llm=True,
            shortlist_top_k=shortlist,
        )

    async def _resolve_job(
        self, job_id: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        job_data, tier = await self.kg_repository.get_job_or_listing(job_id)
        if job_data:
            return job_data, tier or "career"
        listing_row = await self.job_listing_repository.get_by_id(job_id)
        if listing_row:
            data = listing_to_dict(listing_row)
            data["required_skills"] = seed_required_skills(
                data.get("required_skills"),
                f"{data.get('title') or ''}\n{data.get('description') or ''}".strip(),
                await self._known_skill_names(),
            )
            return data, "staging"
        return None, None

    async def _known_skill_names(self) -> list[str]:
        try:
            return await self.kg_repository.list_skill_names()
        except Exception as exc:
            logger.warning(
                "Failed to load known skill names for heuristic extraction: %s", exc
            )
            return []

    def _overlap_match(
        self,
        offer: JobOfferRead,
        user_skill_names: list[str],
        cached: Any,
        fingerprint: str,
    ) -> JobMatchResponse:
        overlap = compute_skill_match(
            user_skill_names, list(offer.required_skills or [])
        )
        if cached:
            return JobMatchResponse(
                job_offer=offer,
                score=float(cached.match_score) / 100.0,
                matching_skills=list(cached.matching_skills or []),
                missing_skills=list(cached.missing_skills or []),
                justification=str(cached.justification or ""),
                quick_score=float(overlap.match_score) / 100.0,
                is_stale=cached.profile_fingerprint != fingerprint,
                matched_at=cached.matched_at.replace(tzinfo=UTC)
                if cached.matched_at and cached.matched_at.tzinfo is None
                else cached.matched_at,
                source=cached.source
                if cached.source in {"overlap", "llm"}
                else "overlap",  # type: ignore[arg-type]
            )
        return JobMatchResponse(
            job_offer=offer,
            score=float(overlap.match_score) / 100.0,
            matching_skills=list(overlap.matching_skills),
            missing_skills=list(overlap.missing_skills),
            justification="",
            quick_score=float(overlap.match_score) / 100.0,
            is_stale=False,
            matched_at=None,
            source="none",
        )

    def _to_job_read(
        self,
        data: dict[str, Any],
        tier: str,
    ) -> JobOfferRead:
        resolved_tier: JobTier = "career" if tier == "career" else "staging"
        skills = data.get("required_skills") or []
        if not isinstance(skills, list):
            skills = []
        return JobOfferRead(
            id=str(data.get("id", "")),
            title=str(data.get("title", "")),
            company=str(data.get("company", "")),
            url=str(data.get("url", "")),
            description=str(data.get("description", "")),
            required_skills=canonicalize_skill_list([str(s) for s in skills]),
            scraped_at=self._parse_scraped_at(data.get("scraped_at")),
            tier=resolved_tier,
            location=str(data.get("location") or ""),
            salary_range=data.get("salary_range"),
            job_type=data.get("job_type"),
            source=data.get("source"),
            seniority=data.get("seniority"),
            min_experience_years=data.get("min_experience_years"),
            max_experience_years=data.get("max_experience_years"),
        )

    def _parse_scraped_at(self, scraped_at: object) -> datetime:
        parsed: datetime | None = None
        if isinstance(scraped_at, datetime):
            parsed = scraped_at
        elif isinstance(scraped_at, str):
            try:
                parsed = datetime.fromisoformat(scraped_at)
            except ValueError:
                parsed = None

        if parsed is None:
            parsed = datetime.now(UTC)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed


# Re-export for callers/tests that catch budget errors via the service module.
__all__ = ["JobService", "MatchBudgetExceeded"]
