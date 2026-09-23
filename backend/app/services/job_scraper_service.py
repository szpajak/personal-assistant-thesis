"""Service for scraping and processing job offers."""

from __future__ import annotations

import logging
from collections import defaultdict

import httpx

from ..config import settings
from ..db.job_listing_repository import JobListingRepository
from ..kg.ingestion import KGIngestion
from ..kg.repository import KGRepository
from ..schemas.job_scraping import (
    JobScrapeRequest,
    JobScrapeRunResult,
    ScrapedJob,
    UpsertAction,
)
from ..utils.job_level import infer_experience_years, infer_seniority
from ..utils.job_url import normalize_job_url
from ..utils.skill_extract import seed_required_skills
from .jobspy_adapter import JobSearchFilters, JobSpyAdapter

logger = logging.getLogger(__name__)


class JobScraperService:
    """Scrape job boards into the Postgres staging table (``ScrapedJobListing``).

    Listings never touch the knowledge graph until a user explicitly
    promotes/saves one (see ``KGIngestion.promote_job``). ``kg_repository``
    is used only to read Skill names for heuristic extraction; we never
    write embeddings or REQUIRES edges during scrape.
    """

    def __init__(
        self,
        job_listing_repository: JobListingRepository,
        kg_ingestion: KGIngestion | None = None,
        jobspy_adapter: JobSpyAdapter | None = None,
        kg_repository: KGRepository | None = None,
    ) -> None:
        """Initialize job scraper service.

        Args:
            job_listing_repository: Postgres repository for staging listings
            kg_ingestion: KG ingestion service (only used by ``update_job_status``)
            jobspy_adapter: Optional adapter for job board scraping
            kg_repository: Optional KG repo used to load known skill names

        """
        self.job_listing_repository = job_listing_repository
        self.kg_ingestion = kg_ingestion
        self.jobspy_adapter = jobspy_adapter or JobSpyAdapter()
        self.kg_repository = kg_repository
        self._known_skill_names_cache: list[str] | None = None

    @staticmethod
    def filters_from_request(request: JobScrapeRequest | None) -> JobSearchFilters:
        """Build jobspy filters from an API request, falling back to env defaults."""
        if request is None:
            return JobSearchFilters.from_settings()

        sites = tuple(site.strip() for site in (request.sites or []) if site.strip())
        if not sites:
            sites = tuple(settings.job_search_sites_list)

        return JobSearchFilters(
            search_terms=(request.search_term.strip(),),
            sites=sites,
            location=(request.location or settings.job_search_location).strip(),
            country=(request.country or settings.job_country_indeed).strip(),
            job_type=request.job_type,
            is_remote=request.is_remote,
            hours_old=request.hours_old,
            distance=request.distance,
            results_wanted=min(
                50,
                max(1, request.results_wanted or settings.job_results_wanted),
            ),
        )

    async def scrape_job_boards(
        self,
        request: JobScrapeRequest | None = None,
    ) -> JobScrapeRunResult:
        """Scrape job boards and ingest offers.

        When ``request`` is provided (on-demand search from the app), its
        filters are forwarded to jobspy2. RemoteOK is only included when
        explicitly requested (or when running the legacy env-driven scrape).

        Returns:
            Scrape run result with stats and ingested job IDs

        """
        result = JobScrapeRunResult()
        filters = self.filters_from_request(request)
        include_remoteok = (
            request.include_remoteok if request is not None else settings.job_scrape_remoteok
        )

        if include_remoteok:
            try:
                await self._ingest_remoteok(result, search_term=filters.search_terms[0])
            except Exception as exc:
                logger.error("RemoteOK scraping failed: %s", exc)

        try:
            await self._ingest_jobspy_boards(result, filters=filters)
        except Exception as exc:
            logger.error("Job board scraping failed: %s", exc)

        logger.info("Scrape finished: %s", result.stats.to_dict())
        return result

    async def _ingest_remoteok(
        self,
        result: JobScrapeRunResult,
        search_term: str,
    ) -> None:
        ingested = []
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://remoteok.com/api",
                headers={"User-Agent": "CareerAssistant/1.0"},
            )
            if response.status_code != 200:
                return

            jobs_data = response.json()
            for job in jobs_data[1:11]:
                try:
                    action, job_id = await self._upsert_scraped_job(
                        ScrapedJob(
                            external_id=str(job.get("id", "")),
                            title=job.get("position", "Unknown Position"),
                            company=job.get("company", "Unknown Company"),
                            description=job.get("description", ""),
                            url=job.get("url", ""),
                            location=job.get("location", "Remote"),
                            source="remoteok",
                            search_term=search_term,
                            salary_range=(
                                f"{job.get('salary_min', '')}-{job.get('salary_max', '')}"
                            ),
                        ),
                        required_skills=job.get("tags", []),
                        extract_skills=not job.get("tags"),
                    )
                    self._record_action(result, action, job_id)
                    ingested.append(normalize_job_url(job.get("url", "")) or job.get("url", ""))
                except Exception as exc:
                    logger.error("Failed to ingest RemoteOK job: %s", exc)

        expired = await self.job_listing_repository.expire_stale(
            source="remoteok",
            seen_urls=[url for url in ingested if url],
            ttl_days=settings.job_scrape_ttl_days,
        )
        result.stats.expired += expired

    async def _ingest_jobspy_boards(
        self,
        result: JobScrapeRunResult,
        filters: JobSearchFilters,
    ) -> None:
        scraped_jobs = await self.jobspy_adapter.scrape_all(filters=filters)
        seen_by_source: dict[str, list[str]] = defaultdict(list)

        # Upserts MUST be sequential: a single AsyncSession/asyncpg connection
        # cannot run concurrent operations ("another operation is in progress").
        for job in scraped_jobs:
            await self._process_scraped_job(job, result, seen_by_source)

        for source, urls in seen_by_source.items():
            expired = await self.job_listing_repository.expire_stale(
                source=source,
                seen_urls=urls,
                ttl_days=settings.job_scrape_ttl_days,
            )
            result.stats.expired += expired

    async def _process_scraped_job(
        self,
        job: ScrapedJob,
        result: JobScrapeRunResult,
        seen_by_source: dict[str, list[str]],
    ) -> None:
        try:
            action, job_id = await self._upsert_scraped_job(
                job,
                required_skills=[],
                extract_skills=True,
            )
            self._record_action(result, action, job_id)
            if job.url:
                seen_by_source[job.source].append(normalize_job_url(job.url) or job.url)
        except Exception as exc:
            logger.error("Failed to ingest %s job '%s': %s", job.source, job.title, exc)

    async def _upsert_scraped_job(
        self,
        job: ScrapedJob,
        required_skills: list[str],
        extract_skills: bool,
    ) -> tuple[UpsertAction, str]:
        # Staging only: never embed or create REQUIRES edges during scrape.
        # Heuristic skill extraction is cheap (regex vs known names/aliases)
        # and is what powers estimated overlap on the scraped-offers list
        # before a listing is promoted.
        skill_text = f"{job.title}\n{job.description}".strip()
        known_names: list[str] = []
        if extract_skills:
            known_names = await self._known_skill_names()
        skills = seed_required_skills(
            required_skills,
            skill_text if extract_skills else "",
            known_names,
        )
        seniority = infer_seniority(job.title, job.description)
        min_years, max_years = infer_experience_years(job.description)
        return await self.job_listing_repository.upsert_by_url(
            title=job.title,
            company=job.company,
            description=job.description,
            required_skills=skills,
            metadata={
                "url": job.url,
                "location": job.location,
                "salary_range": job.salary_range,
                "source": job.source,
                "external_id": job.external_id,
                "posted_at": job.posted_at,
                "job_type": job.job_type,
                "search_term": job.search_term,
            },
            ttl_days=settings.job_scrape_ttl_days,
            seniority=seniority,
            min_experience_years=min_years,
            max_experience_years=max_years,
        )

    async def _known_skill_names(self) -> list[str]:
        if self._known_skill_names_cache is not None:
            return self._known_skill_names_cache
        if self.kg_repository is None:
            self._known_skill_names_cache = []
            return self._known_skill_names_cache
        try:
            self._known_skill_names_cache = await self.kg_repository.list_skill_names()
        except Exception as exc:
            logger.warning(
                "Failed to load known skill names during scrape: %s", exc
            )
            self._known_skill_names_cache = []
        return self._known_skill_names_cache

    def _record_action(
        self,
        result: JobScrapeRunResult,
        action: UpsertAction,
        job_id: str,
    ) -> None:
        if action == UpsertAction.INGESTED:
            result.stats.ingested += 1
            result.job_ids.append(job_id)
        elif action == UpsertAction.UPDATED:
            result.stats.updated += 1
            result.job_ids.append(job_id)
        else:
            result.stats.skipped += 1

    async def update_job_status(
        self,
        job_id: str,
        status: str,
    ) -> None:
        """Update job offer status in KG.

        Args:
            job_id: Job offer ID
            status: New status (active, archived, expired)

        """
        try:
            repo = self.kg_ingestion.kg_repository
            await repo.upsert_node("JobOffer", {"id": job_id, "status": status})
            logger.info(f"Updated job {job_id} status to {status}")
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")
            raise
