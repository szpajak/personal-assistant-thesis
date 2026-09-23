from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.job_listing_repository import JobListingRepository
from app.models.base import Base
from app.schemas.job_scraping import UpsertAction


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """In-memory SQLite session - real SQL semantics without a live Postgres."""
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def repo(db_session: AsyncSession) -> JobListingRepository:
    return JobListingRepository(db=db_session)


@pytest.mark.asyncio
async def test_upsert_by_url_inserts_new_listing(repo: JobListingRepository) -> None:
    action, listing_id = await repo.upsert_by_url(
        title="Backend Engineer",
        company="Acme",
        description="Build APIs with Python",
        required_skills=["Python", "FastAPI"],
        metadata={
            "url": "https://example.com/jobs/1",
            "source": "indeed",
            "location": "Remote",
        },
        seniority="mid",
        min_experience_years=2,
        max_experience_years=5,
    )

    assert action == UpsertAction.INGESTED
    stored = await repo.get_by_id(listing_id)
    assert stored is not None
    assert stored.title == "Backend Engineer"
    assert stored.seniority == "mid"
    assert stored.min_experience_years == 2
    assert stored.max_experience_years == 5


@pytest.mark.asyncio
async def test_upsert_by_url_skips_fresh_unchanged_listing(
    repo: JobListingRepository,
) -> None:
    metadata = {"url": "https://example.com/jobs/2", "source": "indeed"}
    await repo.upsert_by_url(
        title="Engineer",
        company="Acme",
        description="Same",
        required_skills=["Python"],
        metadata=metadata,
    )

    action, _ = await repo.upsert_by_url(
        title="Engineer",
        company="Acme",
        description="Same",
        required_skills=["Python"],
        metadata=metadata,
    )

    assert action == UpsertAction.SKIPPED


@pytest.mark.asyncio
async def test_upsert_by_url_updates_when_description_changes(
    repo: JobListingRepository,
) -> None:
    metadata = {"url": "https://example.com/jobs/3", "source": "indeed"}
    _, listing_id = await repo.upsert_by_url(
        title="Engineer",
        company="Acme",
        description="Old description",
        required_skills=["Python"],
        metadata=metadata,
    )

    action, updated_id = await repo.upsert_by_url(
        title="Engineer",
        company="Acme",
        description="New description",
        required_skills=["Python", "Docker"],
        metadata=metadata,
    )

    assert action == UpsertAction.UPDATED
    assert updated_id == listing_id
    stored = await repo.get_by_id(listing_id)
    assert stored is not None
    assert stored.description == "New description"
    assert stored.required_skills == ["Python", "Docker"]


@pytest.mark.asyncio
async def test_list_listings_filters_by_search_and_seniority(
    repo: JobListingRepository,
) -> None:
    await repo.upsert_by_url(
        title="Junior Python Developer",
        company="Acme",
        description="Entry-level role",
        required_skills=["Python"],
        metadata={"url": "https://example.com/jobs/junior", "source": "indeed"},
        seniority="junior",
    )
    await repo.upsert_by_url(
        title="Senior Backend Engineer",
        company="Beta",
        description="Lead the team",
        required_skills=["Python"],
        metadata={"url": "https://example.com/jobs/senior", "source": "indeed"},
        seniority="senior",
    )

    junior_only = await repo.list_listings(seniority="junior")
    assert len(junior_only) == 1
    assert junior_only[0].title == "Junior Python Developer"

    by_search = await repo.list_listings(search="backend")
    assert len(by_search) == 1
    assert by_search[0].company == "Beta"


@pytest.mark.asyncio
async def test_list_listings_filters_by_experience_bracket(
    repo: JobListingRepository,
) -> None:
    await repo.upsert_by_url(
        title="Entry role",
        company="Acme",
        description="",
        required_skills=[],
        metadata={"url": "https://example.com/jobs/entry", "source": "indeed"},
        min_experience_years=0,
        max_experience_years=2,
    )
    await repo.upsert_by_url(
        title="Senior role",
        company="Acme",
        description="",
        required_skills=[],
        metadata={"url": "https://example.com/jobs/senior-exp", "source": "indeed"},
        min_experience_years=5,
        max_experience_years=None,
    )

    bracket_0_2 = await repo.list_listings(min_years=0, max_years=2)
    assert {j.title for j in bracket_0_2} == {"Entry role"}

    bracket_5_plus = await repo.list_listings(min_years=5, max_years=None)
    assert {j.title for j in bracket_5_plus} == {"Senior role"}


@pytest.mark.asyncio
async def test_delete_by_id_removes_row(repo: JobListingRepository) -> None:
    _, listing_id = await repo.upsert_by_url(
        title="Engineer",
        company="Acme",
        description="",
        required_skills=[],
        metadata={"url": "https://example.com/jobs/delete-me", "source": "indeed"},
    )

    deleted = await repo.delete_by_id(listing_id)
    assert deleted is True
    assert await repo.get_by_id(listing_id) is None
    assert await repo.delete_by_id(listing_id) is False


@pytest.mark.asyncio
async def test_expire_stale_marks_old_unseen_listings(
    repo: JobListingRepository,
) -> None:
    _, stale_id = await repo.upsert_by_url(
        title="Old role",
        company="Acme",
        description="",
        required_skills=[],
        metadata={"url": "https://example.com/jobs/stale", "source": "indeed"},
    )
    stale = await repo.get_by_id(stale_id)
    assert stale is not None
    stale.scraped_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30)
    await repo.db.commit()

    _, fresh_id = await repo.upsert_by_url(
        title="Fresh role",
        company="Acme",
        description="",
        required_skills=[],
        metadata={"url": "https://example.com/jobs/fresh", "source": "indeed"},
    )

    expired_count = await repo.expire_stale(source="indeed", seen_urls=[], ttl_days=7)

    assert expired_count == 1
    stale_after = await repo.get_by_id(stale_id)
    fresh_after = await repo.get_by_id(fresh_id)
    assert stale_after is not None and stale_after.status == "expired"
    assert fresh_after is not None and fresh_after.status == "active"
