from __future__ import annotations

from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from app.config import settings
from app.schemas.job_scraping import UpsertAction
from app.services.jobspy_adapter import (
    JobSearchFilters,
    JobSpyAdapter,
    _map_row_to_scraped_job,
    _scrape_jobs_sync,
)


def _llm_response(content: str) -> AsyncMock:
    response = AsyncMock()
    response.content = content
    return response


def test_map_row_to_scraped_job_maps_core_fields() -> None:
    row = {
        "id": "123",
        "site": "linkedin",
        "job_url": "https://linkedin.com/jobs/view/123",
        "title": "Python Developer",
        "company": "Acme Corp",
        "location": "Remote",
        "description": "Build APIs",
        "job_type": "fulltime",
        "min_amount": 100000,
        "max_amount": 120000,
        "currency": "USD",
        "interval": "yearly",
        "date_posted": "2026-01-01",
    }

    job = _map_row_to_scraped_job(row, search_term="Python Developer")

    assert job is not None
    assert job.external_id == "123"
    assert job.source == "linkedin"
    assert job.url == "https://linkedin.com/jobs/view/123"
    assert job.title == "Python Developer"
    assert job.company == "Acme Corp"
    assert job.search_term == "Python Developer"
    assert job.salary_range is not None
    assert "100000" in job.salary_range


def test_map_row_to_scraped_job_skips_incomplete_rows() -> None:
    job = _map_row_to_scraped_job({"title": "", "company": "Acme"}, search_term="x")
    assert job is None


@pytest.mark.asyncio
async def test_scrape_site_uses_thread_pool_and_maps_rows() -> None:
    adapter = JobSpyAdapter()
    df = pd.DataFrame(
        [
            {
                "id": "1",
                "site": "indeed",
                "job_url": "https://indeed.com/view/1",
                "title": "Backend Engineer",
                "company": "Beta Inc",
                "location": "London",
                "description": "FastAPI work",
            }
        ]
    )

    with patch(
        "app.services.jobspy_adapter._scrape_jobs_sync",
        return_value=df,
    ) as mock_sync:
        jobs = await adapter.scrape_site(site="indeed", search_term="Backend Engineer")

    mock_sync.assert_called_once()
    assert mock_sync.call_args.args[0] == "indeed"
    assert mock_sync.call_args.args[1] == "Backend Engineer"
    assert len(jobs) == 1
    assert jobs[0].source == "indeed"


def test_scrape_jobs_sync_paginates_in_batches_with_sleep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test: previously this called `from jobspy import scrape_jobs`,
    but no `jobspy` module exists (only `jobspy2`), so every real scrape
    raised ModuleNotFoundError and silently produced zero results. It must
    now import from `jobspy2`, and fetch results in rate-limited batches.
    """
    monkeypatch.setattr(settings, "job_results_wanted", 5)
    monkeypatch.setattr(settings, "job_scrape_batch_size", 2)
    monkeypatch.setattr(settings, "job_scrape_sleep_seconds", 1)
    monkeypatch.setattr(settings, "job_scrape_max_retries", 3)

    batch1 = pd.DataFrame(
        [{"title": "A", "company": "X"}, {"title": "B", "company": "Y"}]
    )
    batch2 = pd.DataFrame(
        [{"title": "C", "company": "Z"}, {"title": "D", "company": "W"}]
    )
    batch3 = pd.DataFrame([{"title": "E", "company": "V"}])
    mock_scrape_jobs = MagicMock(side_effect=[batch1, batch2, batch3])
    filters = JobSearchFilters.from_settings()

    with (
        patch("jobspy2.scrape_jobs", mock_scrape_jobs),
        patch("app.services.jobspy_adapter.time.sleep") as mock_sleep,
    ):
        result = _scrape_jobs_sync("linkedin", "Python Developer", filters)

    assert len(result) == 5
    assert mock_scrape_jobs.call_count == 3
    offsets = [call.kwargs["offset"] for call in mock_scrape_jobs.call_args_list]
    assert offsets == [0, 2, 4]
    # Slept between batch 1->2 and 2->3, but not after the final batch.
    assert mock_sleep.call_count == 2
    mock_sleep.assert_called_with(1)


def test_scrape_jobs_sync_retries_with_backoff_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "job_results_wanted", 2)
    monkeypatch.setattr(settings, "job_scrape_batch_size", 2)
    monkeypatch.setattr(settings, "job_scrape_sleep_seconds", 1)
    monkeypatch.setattr(settings, "job_scrape_max_retries", 3)

    good_batch = pd.DataFrame(
        [{"title": "A", "company": "X"}, {"title": "B", "company": "Y"}]
    )
    mock_scrape_jobs = MagicMock(side_effect=[RuntimeError("blocked"), good_batch])
    filters = JobSearchFilters.from_settings()

    with (
        patch("jobspy2.scrape_jobs", mock_scrape_jobs),
        patch("app.services.jobspy_adapter.time.sleep") as mock_sleep,
    ):
        result = _scrape_jobs_sync("linkedin", "Python Developer", filters)

    assert len(result) == 2
    assert mock_scrape_jobs.call_count == 2
    # Backoff after the first failed attempt: sleep_seconds * attempt(1).
    mock_sleep.assert_any_call(1)


def test_scrape_jobs_sync_gives_up_after_max_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "job_results_wanted", 5)
    monkeypatch.setattr(settings, "job_scrape_batch_size", 5)
    monkeypatch.setattr(settings, "job_scrape_sleep_seconds", 1)
    monkeypatch.setattr(settings, "job_scrape_max_retries", 2)

    mock_scrape_jobs = MagicMock(side_effect=RuntimeError("blocked"))
    filters = JobSearchFilters.from_settings()

    with (
        patch("jobspy2.scrape_jobs", mock_scrape_jobs),
        patch("app.services.jobspy_adapter.time.sleep"),
    ):
        result = _scrape_jobs_sync("linkedin", "Python Developer", filters)

    assert result.empty
    assert mock_scrape_jobs.call_count == 2


def test_scrape_jobs_sync_forwards_custom_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "job_results_wanted", 2)
    monkeypatch.setattr(settings, "job_scrape_batch_size", 2)
    monkeypatch.setattr(settings, "job_scrape_sleep_seconds", 0)
    monkeypatch.setattr(settings, "job_scrape_max_retries", 1)

    mock_scrape_jobs = MagicMock(
        return_value=pd.DataFrame([{"title": "A", "company": "X"}])
    )
    filters = JobSearchFilters(
        search_terms=("Backend Engineer",),
        sites=("indeed",),
        location="Warsaw, Poland",
        country="Poland",
        job_type="fulltime",
        is_remote=True,
        hours_old=72,
        distance=25,
        results_wanted=2,
    )

    with (
        patch("jobspy2.scrape_jobs", mock_scrape_jobs),
        patch("app.services.jobspy_adapter.time.sleep"),
    ):
        _scrape_jobs_sync("indeed", "Backend Engineer", filters)

    kwargs = mock_scrape_jobs.call_args.kwargs
    assert kwargs["location"] == "Warsaw, Poland"
    assert kwargs["country_indeed"] == "Poland"
    assert kwargs["job_type"] == "fulltime"
    assert kwargs["is_remote"] is True
    assert kwargs["hours_old"] == 72
    assert kwargs["distance"] == 25


@pytest.mark.asyncio
async def test_scrape_all_waits_between_repeated_requests_to_same_site(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LinkedIn in particular blocks aggressively on request bursts, so
    repeated requests to the *same* site (across different search terms)
    must be spaced out; different sites should not wait on each other.
    """
    monkeypatch.setattr(settings, "job_search_terms", "Python Developer,Data Engineer")
    monkeypatch.setattr(settings, "job_search_sites", "linkedin")
    monkeypatch.setattr(settings, "job_scrape_sleep_seconds", 5)

    adapter = JobSpyAdapter()
    adapter.scrape_site = AsyncMock(return_value=[])  # type: ignore[method-assign]

    with patch(
        "app.services.jobspy_adapter.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        await adapter.scrape_all()

    assert adapter.scrape_site.await_count == 2
    # No wait needed before the first request; the repeated one waits.
    mock_sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_scraped_job_extracts_heuristic_skills() -> None:
    from app.schemas.job_scraping import ScrapedJob
    from app.services.job_scraper_service import JobScraperService

    repo = MagicMock()
    repo.upsert_by_url = AsyncMock(return_value=(UpsertAction.INGESTED, "job-1"))
    service = JobScraperService(job_listing_repository=repo)
    job = ScrapedJob(
        external_id="1",
        title="Python Developer",
        company="Acme",
        description="We need Python, Docker, and Kubernetes experience.",
        url="https://example.com/1",
        location="Remote",
        source="indeed",
        search_term="Python Developer",
    )

    action, job_id = await service._upsert_scraped_job(
        job, required_skills=[], extract_skills=True
    )

    assert action == UpsertAction.INGESTED
    assert job_id == "job-1"
    skills = repo.upsert_by_url.await_args.kwargs["required_skills"]
    assert "Python" in skills
    assert "Docker" in skills
    assert "Kubernetes" in skills


@pytest.mark.asyncio
async def test_upsert_scraped_job_keeps_provided_skills_when_extract_disabled() -> None:
    from app.schemas.job_scraping import ScrapedJob
    from app.services.job_scraper_service import JobScraperService

    repo = MagicMock()
    repo.upsert_by_url = AsyncMock(return_value=(UpsertAction.INGESTED, "job-2"))
    service = JobScraperService(job_listing_repository=repo)
    job = ScrapedJob(
        external_id="2",
        title="Java Developer",
        company="Acme",
        description="We need Python and Docker.",
        url="https://example.com/2",
        location="Remote",
        source="remoteok",
        search_term="Java",
    )

    await service._upsert_scraped_job(
        job, required_skills=["Java"], extract_skills=False
    )

    assert repo.upsert_by_url.await_args.kwargs["required_skills"] == ["Java"]


@pytest.mark.asyncio
async def test_upsert_job_offer_skips_fresh_unchanged_job() -> None:
    from app.kg.ingestion import KGIngestion

    repo = MagicMock()
    repo.get_job_by_url = AsyncMock(
        return_value={
            "id": "job-1",
            "description": "Same description",
            "required_skills": ["Python"],
            "scraped_at": "2099-01-01T00:00:00+00:00",
        }
    )
    embeddings = MagicMock()
    embeddings.embed_text = AsyncMock(return_value=[0.1, 0.2])

    ingestion = KGIngestion(
        kg_repository=repo, embeddings=embeddings, scrape_ttl_days=7
    )
    action, job_id = await ingestion.upsert_job_offer(
        title="Engineer",
        company="Acme",
        description="Same description",
        required_skills=["Python"],
        metadata={"url": "https://example.com/job/1", "source": "linkedin"},
        extract_skills=False,
    )

    assert action == UpsertAction.SKIPPED
    assert job_id == "job-1"
    repo.upsert_node.assert_not_called()


@pytest.mark.asyncio
async def test_promote_job_converts_listing_to_offer() -> None:
    """Scraped listings now live in Postgres - the caller (JobService) fetches
    the row and passes it in directly, so ``promote_job`` never touches a
    ``JobListing`` Neo4j node anymore.
    """
    from app.kg.ingestion import KGIngestion

    listing = {
        "id": "job-1",
        "title": "Engineer",
        "company": "Acme Corp",
        "description": "Build services with Python",
        "required_skills": ["Python"],
        "url": "https://example.com/job/1",
        "source": "indeed",
        "scraped_at": "2026-01-01T00:00:00+00:00",
    }
    repo = MagicMock()
    # get_node call order: JobOffer check (None), Company lookup (None),
    # Skill lookup for "Python" (None).
    repo.get_node = AsyncMock(side_effect=[None, None, None])
    repo.upsert_node = AsyncMock()
    repo.upsert_relationship = AsyncMock()

    embeddings = MagicMock()
    embeddings.embed_text = AsyncMock(return_value=[0.1, 0.2, 0.3])

    with (
        patch("app.kg.ingestion.create_company_enrichment_chain") as mock_chain_factory,
        patch("app.kg.ingestion.create_job_analysis_chain") as mock_analysis_factory,
        patch("app.kg.ingestion.asyncio.sleep", new=AsyncMock()),
    ):
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = _llm_response(
            '{"industry": "", "website": ""}'
        )
        mock_chain_factory.return_value = mock_chain

        # Simulate the analysis LLM being unavailable (even after retries) -
        # promote_job must fall back to the heuristic seed
        # (required_skills/seniority heuristics) instead of failing the
        # whole promote.
        mock_analysis_chain = AsyncMock()
        mock_analysis_chain.ainvoke.side_effect = RuntimeError("llm down")
        mock_analysis_factory.return_value = mock_analysis_chain

        ingestion = KGIngestion(
            kg_repository=repo, embeddings=embeddings, scrape_ttl_days=7
        )
        props, newly = await ingestion.promote_job(
            job_id="job-1", listing=listing, person_id="user_1"
        )

    assert newly is True
    assert props["id"] == "job-1"
    assert props["required_skills"] == ["Python"]
    # One embedding for the job offer itself, one for the newly-created
    # "Python" Skill node (get_node returns None for it, so it doesn't exist
    # yet and needs a fresh embedding).
    assert embeddings.embed_text.await_count == 2
    repo.upsert_node.assert_any_call("JobOffer", ANY)
    repo.upsert_node.assert_any_call("Person", {"id": "user_1"})
    repo.upsert_relationship.assert_any_call(
        from_label="Person",
        from_id="user_1",
        relationship_type="SAVED",
        to_label="JobOffer",
        to_id="job-1",
    )


@pytest.mark.asyncio
async def test_promote_job_raises_when_neither_offer_nor_listing_exists() -> None:
    from app.kg.ingestion import KGIngestion

    repo = MagicMock()
    repo.get_node = AsyncMock(return_value=None)
    embeddings = MagicMock()

    ingestion = KGIngestion(
        kg_repository=repo, embeddings=embeddings, scrape_ttl_days=7
    )

    with pytest.raises(ValueError):
        await ingestion.promote_job(job_id="missing", listing={})


@pytest.mark.asyncio
async def test_upsert_job_offer_creates_new_job_with_company_link() -> None:
    from app.kg.ingestion import KGIngestion

    repo = MagicMock()
    repo.get_job_by_url = AsyncMock(return_value=None)
    repo.get_node = AsyncMock(return_value=None)
    repo.upsert_node = AsyncMock()
    repo.upsert_relationship = AsyncMock()

    embeddings = MagicMock()
    embeddings.embed_text = AsyncMock(return_value=[0.1, 0.2, 0.3])

    with patch(
        "app.kg.ingestion.create_company_enrichment_chain"
    ) as mock_chain_factory:
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = _llm_response(
            '{"industry": "", "website": ""}'
        )
        mock_chain_factory.return_value = mock_chain

        ingestion = KGIngestion(
            kg_repository=repo, embeddings=embeddings, scrape_ttl_days=7
        )
        action, job_id = await ingestion.upsert_job_offer(
            title="Engineer",
            company="Acme Corp",
            description="Build services",
            required_skills=["Python", "Neo4j"],
            metadata={
                "url": "https://example.com/job/2",
                "source": "indeed",
                "external_id": "abc",
            },
            extract_skills=False,
        )

    assert action == UpsertAction.INGESTED
    assert job_id
    repo.upsert_node.assert_any_call("JobOffer", ANY)
    repo.upsert_node.assert_any_call(
        "Company",
        {"id": "company_acme_corp", "name": "Acme Corp", "industry": "", "website": ""},
    )
    repo.upsert_relationship.assert_any_call(
        from_label="JobOffer",
        from_id=job_id,
        relationship_type="POSTED_BY",
        to_label="Company",
        to_id="company_acme_corp",
    )


@pytest.mark.asyncio
async def test_get_market_demand_aggregates_required_skills() -> None:
    from app.kg.repository import KGRepository

    repo = KGRepository()
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.data = AsyncMock(
        return_value=[{"name": "Python", "demand": 3}, {"name": "Neo4j", "demand": 2}]
    )
    mock_session.run.return_value = mock_result

    mock_driver = MagicMock()
    mock_driver.session.return_value.__aenter__.return_value = mock_session

    with patch("app.kg.repository.get_neo4j_driver", return_value=mock_driver):
        demand = await repo.get_market_demand(limit=5)

    assert demand[0]["name"] == "Python"
    assert demand[0]["demand"] == 3
