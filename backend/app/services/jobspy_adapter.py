"""Adapter for job board scraping via jobspy2.

Historically this imported ``from jobspy import scrape_jobs``, but no
``jobspy`` module is actually installed - our declared dependency
(previously ``jobsparser``, now ``jobspy2`` directly) only exposes the
scraper engine as ``jobspy2``. That meant every single LinkedIn/Indeed
scrape attempt raised ``ModuleNotFoundError``, was caught by the per-site
error handler in :meth:`JobSpyAdapter.scrape_all`, and silently produced
zero results - the KG never got anything beyond the RemoteOK feed.

On top of fixing that import, this module reimplements the rate-limiting
technique used by the (CLI-only) ``jobsparser`` tool - fetch results in
small batches with a sleep in between, and retry with backoff on failure -
directly against ``jobspy2.scrape_jobs`` so it runs in-process as part of
our async pipeline instead of shelling out to a CLI that writes CSV files.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import pandas as pd

from ..config import settings
from ..schemas.job_scraping import JobTypeFilter, ScrapedJob

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobSearchFilters:
    """Runtime filters forwarded to jobspy2 ``scrape_jobs``."""

    search_terms: tuple[str, ...]
    sites: tuple[str, ...]
    location: str
    country: str
    job_type: JobTypeFilter | None = None
    is_remote: bool = False
    hours_old: int | None = None
    distance: int | None = None
    results_wanted: int | None = None

    @classmethod
    def from_settings(cls) -> JobSearchFilters:
        return cls(
            search_terms=tuple(settings.job_search_terms_list),
            sites=tuple(settings.job_search_sites_list),
            location=settings.job_search_location,
            country=settings.job_country_indeed,
        )


def _scrape_jobs_sync(site: str, search_term: str, filters: JobSearchFilters) -> pd.DataFrame:
    """Blocking scrape call executed in a worker thread.

    Fetches ``results_wanted`` results in batches of
    ``settings.job_scrape_batch_size``, sleeping ``settings.job_scrape_sleep_seconds``
    between batches so we never hammer LinkedIn/Indeed with one big burst
    request. A batch that fails is retried up to ``settings.job_scrape_max_retries``
    times with linear backoff before we give up and return whatever was
    already collected.
    """
    from jobspy2 import scrape_jobs

    results_wanted = max(1, filters.results_wanted or settings.job_results_wanted)
    batch_size = max(1, settings.job_scrape_batch_size)
    sleep_seconds = max(0, settings.job_scrape_sleep_seconds)
    max_retries = max(1, settings.job_scrape_max_retries)

    base_kwargs: dict[str, Any] = {
        "site_name": [site],
        "search_term": search_term,
        "location": filters.location,
        "linkedin_fetch_description": settings.job_linkedin_fetch_description,
        "country_indeed": filters.country,
        "is_remote": filters.is_remote,
    }
    if filters.job_type:
        base_kwargs["job_type"] = filters.job_type
    if filters.hours_old is not None:
        base_kwargs["hours_old"] = filters.hours_old
    if filters.distance is not None:
        base_kwargs["distance"] = filters.distance
    if settings.job_proxies_list:
        base_kwargs["proxies"] = settings.job_proxies_list

    batches: list[pd.DataFrame] = []
    offset = 0
    total_rows = 0

    while total_rows < results_wanted:
        wanted_this_batch = min(batch_size, results_wanted - total_rows)
        batch_df: pd.DataFrame | None = None

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    "jobspy2: scraping %s for '%s' (offset=%d, wanted=%d, attempt=%d/%d)",
                    site,
                    search_term,
                    offset,
                    wanted_this_batch,
                    attempt,
                    max_retries,
                )
                batch_df = scrape_jobs(
                    **base_kwargs,
                    results_wanted=wanted_this_batch,
                    offset=offset,
                )
                break
            except Exception as exc:
                if attempt >= max_retries:
                    logger.error(
                        "jobspy2: giving up on %s/'%s' after %d attempt(s): %s",
                        site,
                        search_term,
                        attempt,
                        exc,
                    )
                    batch_df = None
                    break
                backoff = sleep_seconds * attempt
                logger.warning(
                    "jobspy2: batch for %s/'%s' failed (attempt %d/%d): %s - retrying in %ds",
                    site,
                    search_term,
                    attempt,
                    max_retries,
                    exc,
                    backoff,
                )
                time.sleep(backoff)

        if batch_df is None or batch_df.empty:
            break

        batches.append(batch_df)
        total_rows += len(batch_df)
        offset += wanted_this_batch

        if len(batch_df) < wanted_this_batch or total_rows >= results_wanted:
            # No more results available for this site/term - stop early.
            break

        logger.info(
            "jobspy2: sleeping %ds before next batch (%s/'%s')",
            sleep_seconds,
            site,
            search_term,
        )
        time.sleep(sleep_seconds)

    if not batches:
        return pd.DataFrame()
    return pd.concat(batches, ignore_index=True)


def _safe_str(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _format_salary(row: dict[str, Any]) -> str | None:
    min_amount = row.get("min_amount")
    max_amount = row.get("max_amount")
    currency = _safe_str(row.get("currency"))
    interval = _safe_str(row.get("interval"))

    if min_amount is None and max_amount is None:
        return None
    if pd.isna(min_amount) and pd.isna(max_amount):
        return None

    min_str = "" if pd.isna(min_amount) else str(min_amount)
    max_str = "" if pd.isna(max_amount) else str(max_amount)
    parts = [f"{min_str}-{max_str}".strip("-")]
    if currency:
        parts.append(currency)
    if interval:
        parts.append(interval)
    return " ".join(parts)


def _map_row_to_scraped_job(
    row: dict[str, Any],
    search_term: str,
) -> ScrapedJob | None:
    title = _safe_str(row.get("title"))
    company = _safe_str(row.get("company"))
    if not title or not company:
        return None

    source = _safe_str(row.get("site")) or "unknown"
    external_id = _safe_str(row.get("id")) or f"{source}:{title}:{company}"
    url = _safe_str(row.get("job_url"))
    if not url:
        url = f"{source}://job/{external_id}"

    posted_at = row.get("date_posted")
    posted_at_str = None
    if posted_at is not None and not (isinstance(posted_at, float) and pd.isna(posted_at)):
        posted_at_str = str(posted_at)

    return ScrapedJob(
        external_id=external_id,
        title=title,
        company=company,
        description=_safe_str(row.get("description")),
        url=url,
        location=_safe_str(row.get("location")),
        source=source,
        search_term=search_term,
        job_type=_safe_str(row.get("job_type")) or None,
        salary_range=_format_salary(row),
        posted_at=posted_at_str,
    )


class JobSpyAdapter:
    """Scrape job boards using jobspy2, with rate limiting to avoid blocks."""

    async def scrape_all(
        self,
        filters: JobSearchFilters | None = None,
    ) -> list[ScrapedJob]:
        """Scrape sites/terms from ``filters`` (defaults to env settings).

        Requests to the *same* site across different search terms are
        spaced at least ``settings.job_scrape_sleep_seconds`` apart (LinkedIn
        in particular blocks aggressively on bursts of requests from one
        IP); different sites are independent services and are not throttled
        against each other.
        """
        resolved = filters or JobSearchFilters.from_settings()
        scraped_jobs: list[ScrapedJob] = []
        sleep_seconds = max(0, settings.job_scrape_sleep_seconds)
        last_request_at: dict[str, float] = {}

        for search_term in resolved.search_terms:
            for site in resolved.sites:
                last = last_request_at.get(site)
                if last is not None:
                    remaining = sleep_seconds - (time.monotonic() - last)
                    if remaining > 0:
                        logger.info(
                            "Waiting %.0fs before next %s request to avoid rate limiting/blocks",
                            remaining,
                            site,
                        )
                        await asyncio.sleep(remaining)

                try:
                    site_jobs = await self.scrape_site(
                        site=site,
                        search_term=search_term,
                        filters=resolved,
                    )
                    scraped_jobs.extend(site_jobs)
                except Exception as exc:
                    logger.error(
                        "Failed to scrape %s for term '%s': %s",
                        site,
                        search_term,
                        exc,
                    )
                finally:
                    last_request_at[site] = time.monotonic()

        logger.info("Scraped %d jobs from job boards", len(scraped_jobs))
        return scraped_jobs

    async def scrape_site(
        self,
        site: str,
        search_term: str,
        filters: JobSearchFilters | None = None,
    ) -> list[ScrapedJob]:
        """Scrape a single site for one search term."""
        resolved = filters or JobSearchFilters.from_settings()
        df = await asyncio.to_thread(_scrape_jobs_sync, site, search_term, resolved)
        if df is None or df.empty:
            return []

        jobs: list[ScrapedJob] = []
        for row in df.to_dict(orient="records"):
            mapped = _map_row_to_scraped_job(row, search_term=search_term)
            if mapped:
                jobs.append(mapped)
        return jobs
