from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.kg.repository import KGRepository
from app.pipelines.job_match_pipeline import (
    JobMatchPipeline,
    _format_candidate_profile,
    _job_retrieval_query,
)
from app.utils.job_url import normalize_job_url
from app.utils.profile_fingerprint import fingerprint_from_skills
from app.utils.skill_extract import extract_skills_from_text
from app.utils.skill_match import compute_skill_match


@pytest.fixture
def job_match_pipeline(kg_repository: KGRepository) -> JobMatchPipeline:
    return JobMatchPipeline(kg_repository=kg_repository)


def test_compute_skill_match_percentage() -> None:
    result = compute_skill_match(
        user_skills=["Python", "FastAPI", "Neo4j", "Docker"],
        job_skills=["Python", "FastAPI", "Kubernetes", "AWS"],
    )
    assert result.match_score == 50
    assert result.matching_skills == ["FastAPI", "Python"]
    assert result.missing_skills == ["AWS", "Kubernetes"]


def test_compute_skill_match_is_case_insensitive() -> None:
    result = compute_skill_match(
        user_skills=["python", "node.js"],
        job_skills=["Python", "Node.js", "Go"],
    )
    assert result.match_score == 67
    assert set(result.matching_skills) == {"Python", "Node.js"}
    assert result.missing_skills == ["Go"]


def test_compute_skill_match_empty_job_skills() -> None:
    result = compute_skill_match(user_skills=["Python"], job_skills=[])
    assert result.match_score == 0
    assert result.matching_skills == []
    assert result.missing_skills == []


def test_fingerprint_from_skills_is_stable() -> None:
    a = fingerprint_from_skills(
        [
            {"name": "Python", "level": "advanced"},
            {"name": "FastAPI", "level": "intermediate"},
        ]
    )
    b = fingerprint_from_skills(
        [
            {"name": "FastAPI", "level": "intermediate"},
            {"name": "Python", "level": "advanced"},
        ]
    )
    assert a == b
    c = fingerprint_from_skills(
        [
            {"name": "Python", "level": "beginner"},
            {"name": "FastAPI", "level": "intermediate"},
        ]
    )
    assert a != c


def test_normalize_job_url_strips_tracking() -> None:
    url = "https://WWW.LinkedIn.com/jobs/view/123/?utm_source=x&trk=foo&ref=bar"
    assert normalize_job_url(url) == "https://linkedin.com/jobs/view/123"


def test_extract_skills_from_text_finds_known_and_synonyms() -> None:
    text = "We need strong Python, React.js, and K8s experience with Docker."
    found = extract_skills_from_text(text, known_skill_names=["Python", "Docker"])
    assert "Python" in found
    assert "Docker" in found
    assert "React" in found
    assert "Kubernetes" in found


def test_seed_required_skills_keeps_stored_and_extracts_when_empty() -> None:
    from app.utils.skill_extract import seed_required_skills

    stored = seed_required_skills(["Python"], "We need Docker and Kubernetes.")
    assert stored == ["Python"]

    extracted = seed_required_skills(
        [],
        "We need Python, Docker, and Kubernetes.",
        known_skill_names=["Python"],
    )
    assert "Python" in extracted
    assert "Docker" in extracted
    assert "Kubernetes" in extracted


def test_extract_skills_from_text_finds_canonical_names_without_kg() -> None:
    """Scrape has no KG skill list; canonical names + aliases must still fire."""
    found = extract_skills_from_text("We need Python, Docker, and Kubernetes.")
    assert "Python" in found
    assert "Docker" in found
    assert "Kubernetes" in found


def _patch_match_chain(mock_chain: AsyncMock):
    """Patch ``JOB_MATCHING_PROMPT | llm | parser`` to return ``mock_chain``."""
    mock_prompt = MagicMock()
    mock_prompt.__or__.return_value.__or__.return_value = mock_chain
    return patch(
        "app.pipelines.job_match_pipeline.JOB_MATCHING_PROMPT",
        mock_prompt,
    )


@pytest.mark.asyncio
async def test_job_match_pipeline_run_uses_llm_with_skill_levels(
    job_match_pipeline: JobMatchPipeline,
    kg_repository: KGRepository,
) -> None:
    user_id = "user_123"

    kg_repository.get_person_skills = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            {"name": "Python", "level": "advanced"},
            {"name": "FastAPI", "level": "intermediate"},
            {"name": "Docker", "level": "beginner"},
        ]
    )
    kg_repository.get_person_career_brief = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "employment": [
                {
                    "title": "Backend Engineer",
                    "company": "TechCorp",
                    "start_date": "2022-01-01",
                    "end_date": None,
                    "description": "Built FastAPI services in production.",
                    "skills": ["Python", "FastAPI"],
                }
            ],
            "projects": [],
            "certificates": [],
            "education": [],
        }
    )
    kg_repository.query = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            {
                "job": {
                    "id": "job_1",
                    "title": "Backend Dev",
                    "company": "TechCorp",
                    "description": "Python job",
                    "required_skills": ["Python", "FastAPI", "Kubernetes"],
                },
                "linked_skills": ["Python", "Redis"],
            }
        ]
    )

    # No GraphRAG hits for this job -> _build_job_evidence falls back to the
    # full career brief, matching this test's original intent.
    job_match_pipeline.graph_rag.retrieve = AsyncMock(return_value=[])  # type: ignore[method-assign]

    mock_chain = AsyncMock()
    mock_chain.ainvoke.return_value = {
        "match_score": 72,
        "matching_skills": ["Python", "FastAPI"],
        "missing_skills": ["Kubernetes", "Redis"],
        "justification": "Strong Python/FastAPI; missing K8s and Redis.",
    }

    with _patch_match_chain(mock_chain):
        result = await job_match_pipeline.run(user_id, job_ids=["job_1"])

    assert len(result) == 1
    assert result[0]["job_id"] == "job_1"
    assert result[0]["match_score"] == 72
    assert result[0]["source"] == "llm"
    assert set(result[0]["matching_skills"]) == {"Python", "FastAPI"}
    assert set(result[0]["missing_skills"]) == {"Kubernetes", "Redis"}
    assert result[0]["company"] == "TechCorp"

    kg_repository.get_person_skills.assert_awaited_once_with(user_id)
    kg_repository.query.assert_awaited()
    kg_repository.get_person_career_brief.assert_awaited_once_with(user_id)

    invoke_args = mock_chain.ainvoke.await_args.args[0]
    assert "Python (advanced)" in invoke_args["user_skills"]
    assert "FastAPI (intermediate)" in invoke_args["user_skills"]
    assert "Docker (beginner)" in invoke_args["user_skills"]
    assert "Built FastAPI services" in invoke_args["context"]
    assert "TechCorp" in invoke_args["context"]
    # Description is now always sent alongside structured skills.
    assert invoke_args["job_description"] == "Python job"


@pytest.mark.asyncio
async def test_job_match_pipeline_falls_back_when_llm_fails(
    job_match_pipeline: JobMatchPipeline,
    kg_repository: KGRepository,
) -> None:
    kg_repository.get_person_skills = AsyncMock(  # type: ignore[method-assign]
        return_value=[{"name": "Python", "level": "advanced"}, {"name": "FastAPI"}]
    )
    kg_repository.get_person_career_brief = AsyncMock(return_value={})  # type: ignore[method-assign]
    kg_repository.query = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            {
                "job": {
                    "id": "job_1",
                    "title": "Backend Dev",
                    "company": "TechCorp",
                    "description": "Python job",
                    "required_skills": ["Python", "FastAPI", "Kubernetes", "Redis"],
                },
                "linked_skills": [],
            }
        ]
    )
    job_match_pipeline.graph_rag.retrieve = AsyncMock(return_value=[])  # type: ignore[method-assign]

    mock_chain = AsyncMock()
    mock_chain.ainvoke.side_effect = RuntimeError("llm down")

    with _patch_match_chain(mock_chain):
        result = await job_match_pipeline.run("user_123", job_ids=["job_1"])

    assert len(result) == 1
    assert result[0]["match_score"] == 50
    assert result[0]["source"] == "overlap"
    assert set(result[0]["matching_skills"]) == {"Python", "FastAPI"}


@pytest.mark.asyncio
async def test_job_match_pipeline_uses_per_job_graphrag_evidence_when_hits_found(
    job_match_pipeline: JobMatchPipeline,
    kg_repository: KGRepository,
) -> None:
    """When retrieve() returns hits, the per-job evidence excerpt (not the
    full career brief) should be sent to the LLM, and it should be scoped to
    Project/Skill/Certificate (never JobOffer)."""
    user_id = "user_123"

    kg_repository.get_person_skills = AsyncMock(
        return_value=[{"name": "Python", "level": "advanced"}]
    )  # type: ignore[method-assign]
    kg_repository.get_person_career_brief = AsyncMock(return_value={})  # type: ignore[method-assign]
    kg_repository.query = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            {
                "job": {
                    "id": "job_1",
                    "title": "Backend Dev",
                    "company": "TechCorp",
                    "description": "Python job",
                    "required_skills": ["Python"],
                },
                "linked_skills": [],
                "requires_levels": [{"name": "Python", "level": "advanced"}],
            }
        ]
    )

    job_match_pipeline.graph_rag.retrieve = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            {
                "label": "Project",
                "node": {
                    "id": "p1",
                    "title": "Billing API",
                    "description": "FastAPI billing service.",
                },
                "weighted_score": 0.9,
                "related": [],
            }
        ]
    )
    job_match_pipeline.graph_rag.assemble_evidence_chain = AsyncMock(  # type: ignore[method-assign]
        return_value="Evidence chain for skill 'Python':\n  Demonstrated in projects: Billing API"
    )

    mock_chain = AsyncMock()
    mock_chain.ainvoke.return_value = {
        "match_score": 80,
        "matching_skills": ["Python"],
        "missing_skills": [],
        "justification": "Strong Python evidence in Billing API.",
    }

    with _patch_match_chain(mock_chain):
        result = await job_match_pipeline.run(user_id, job_ids=["job_1"])

    assert result[0]["match_score"] == 80
    kg_repository.get_person_career_brief.assert_not_awaited()
    job_match_pipeline.graph_rag.retrieve.assert_awaited_once()
    retrieve_kwargs = job_match_pipeline.graph_rag.retrieve.await_args.kwargs
    assert retrieve_kwargs["labels"] == ["Project", "Skill", "Certificate"]
    assert retrieve_kwargs["person_id"] == user_id
    job_match_pipeline.graph_rag.assemble_evidence_chain.assert_awaited_once_with(
        person_id=user_id, skill_name="Python"
    )

    invoke_args = mock_chain.ainvoke.await_args.args[0]
    assert "Billing API" in invoke_args["context"]
    assert "Demonstrated in projects: Billing API" in invoke_args["context"]
    assert "Python (advanced)" in invoke_args["job_skills"]


@pytest.mark.asyncio
async def test_job_match_pipeline_empty_job_ids_scores_nothing(
    job_match_pipeline: JobMatchPipeline,
    kg_repository: KGRepository,
) -> None:
    kg_repository.get_person_skills = AsyncMock(return_value=[])  # type: ignore[method-assign]
    kg_repository.get_person_career_brief = AsyncMock(return_value={})  # type: ignore[method-assign]
    kg_repository.query = AsyncMock(return_value=[])  # type: ignore[method-assign]

    result = await job_match_pipeline.run("user_123", job_ids=[])
    assert result == []
    kg_repository.query.assert_not_awaited()


@pytest.mark.asyncio
async def test_job_match_pipeline_seeds_skills_for_staging_listings(
    kg_repository: KGRepository,
) -> None:
    """Staging listings often have empty required_skills; fetch must seed them
    with heuristics so overlap matching works before promote.
    """
    from datetime import UTC, datetime
    from types import SimpleNamespace

    listing = SimpleNamespace(
        id="listing-1",
        title="Backend Engineer",
        company="Acme",
        description="Build APIs with Python and Docker. Kubernetes is a plus.",
        required_skills=[],
        url="https://example.com/jobs/1",
        location="Remote",
        salary_range=None,
        source="indeed",
        external_id="abc",
        scraped_at=datetime.now(UTC),
        posted_at=None,
        status="active",
        job_type="fulltime",
        search_term="python",
        seniority="mid",
        min_experience_years=2,
        max_experience_years=5,
    )
    listing_repo = MagicMock()
    listing_repo.get_by_id = AsyncMock(return_value=listing)
    pipeline = JobMatchPipeline(
        kg_repository=kg_repository,
        job_listing_repository=listing_repo,
    )
    kg_repository.get_person_skills = AsyncMock(  # type: ignore[method-assign]
        return_value=[{"name": "Python", "level": "advanced"}, {"name": "Docker"}]
    )
    kg_repository.query = AsyncMock(return_value=[])  # type: ignore[method-assign]
    kg_repository.list_skill_names = AsyncMock(return_value=["Python", "Docker"])  # type: ignore[method-assign]

    result = await pipeline.run("user_123", job_ids=["listing-1"], use_llm=False)

    assert len(result) == 1
    assert result[0]["source"] == "overlap"
    assert result[0]["tier"] == "staging"
    assert result[0]["match_score"] > 0
    assert "Python" in result[0]["required_skills"]
    assert "Docker" in result[0]["matching_skills"]


def test_format_candidate_profile_empty_brief_returns_placeholder() -> None:
    assert _format_candidate_profile({}) == (
        "No roles, projects, certificates, or education recorded."
    )


def test_format_candidate_profile_includes_roles_and_projects() -> None:
    brief = {
        "employment": [
            {
                "title": "Backend Engineer",
                "company": "TechCorp",
                "start_date": "2022-03-01",
                "end_date": None,
                "description": "Built internal APIs and CI pipelines for billing.",
                "skills": ["Python", "FastAPI", "PostgreSQL"],
            }
        ],
        "projects": [
            {
                "title": "Shop API",
                "seniority": "junior",
                "start_date": "2021-01-01",
                "end_date": "2021-06-01",
                "description": "REST shop with JWT auth and order workflow.",
                "skills": ["Python", "FastAPI"],
            }
        ],
        "certificates": [
            {
                "title": "CKA",
                "issuer": "CNCF",
                "issued_at": "2023-01-01",
                "skills": ["Kubernetes"],
            }
        ],
        "education": [
            {
                "degree": "BSc",
                "field_of_study": "Computer Science",
                "institution": "Politechnika",
                "start_date": "2018-01-01",
                "end_date": "2022-01-01",
            }
        ],
    }

    text = _format_candidate_profile(brief)

    assert "ROLES:" in text
    assert "Backend Engineer at TechCorp" in text
    assert "PROJECTS:" in text
    assert "Shop API, junior" in text
    assert "CERTIFICATES:" in text
    assert "CKA (CNCF)" in text
    assert "validates: Kubernetes" in text
    assert "EDUCATION:" in text
    assert "BSc in Computer Science, Politechnika" in text


def test_format_candidate_profile_truncates_to_max_chars() -> None:
    brief = {
        "employment": [
            {
                "title": "Engineer",
                "company": "Corp",
                "start_date": "2020-01-01",
                "end_date": None,
                "description": "x" * 500,
                "skills": ["Python"],
            }
        ],
        "projects": [],
        "certificates": [],
        "education": [],
    }

    text = _format_candidate_profile(brief, max_chars=50)

    assert len(text) == 51  # 50 chars + the truncation ellipsis
    assert text.endswith("…")


def test_job_retrieval_query_uses_title_skills_and_short_snippet() -> None:
    long_description = "Ruby on Rails " + ("boilerplate " * 500)
    query = _job_retrieval_query(
        {
            "title": "Senior Backend Engineer (Ruby)",
            "required_skills": ["Ruby", "Rails", "PostgreSQL"],
            "description": long_description,
        }
    )
    assert "Senior Backend Engineer (Ruby)" in query
    assert "Ruby" in query
    assert "PostgreSQL" in query
    assert len(query) < len(long_description)
    assert query.count("boilerplate") < 50
