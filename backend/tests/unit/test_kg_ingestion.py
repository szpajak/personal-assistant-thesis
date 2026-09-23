from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.kg.ingestion import KGIngestion


def _make_ingestion() -> tuple[KGIngestion, AsyncMock]:
    mock_repo = AsyncMock()
    mock_embeddings = AsyncMock()
    mock_embeddings.embed_text.return_value = [0.1, 0.2, 0.3]
    ingestion = KGIngestion(kg_repository=mock_repo, embeddings=mock_embeddings)
    return ingestion, mock_repo


def _llm_response(content: str) -> AsyncMock:
    response = AsyncMock()
    response.content = content
    return response


@pytest.mark.anyio
async def test_upsert_skill_new_skill_uses_given_level() -> None:
    ingestion, mock_repo = _make_ingestion()
    mock_repo.get_node.return_value = None

    await ingestion._upsert_skill_preserving_existing(
        skill_id="skill_python", name="Python", category="language", level="beginner"
    )

    mock_repo.upsert_node.assert_called_once_with(
        "Skill",
        {
            "id": "skill_python",
            "name": "Python",
            "category": "language",
            "level": "beginner",
            "aliases": [],
            "embedding": [0.1, 0.2, 0.3],
        },
    )


@pytest.mark.anyio
async def test_upsert_skill_bumps_level_up_when_new_project_used_it_more() -> None:
    """Regression test: a Skill's level must represent the HIGHEST
    proficiency ever demonstrated, so a later project at a higher level must
    upgrade an already-stored lower level.
    """
    ingestion, mock_repo = _make_ingestion()
    mock_repo.get_node.return_value = {
        "id": "skill_python",
        "name": "Python",
        "category": "language",
        "level": "beginner",
    }

    await ingestion._upsert_skill_preserving_existing(
        skill_id="skill_python", name="Python", category="language", level="expert"
    )

    _, kwargs = mock_repo.upsert_node.call_args
    assert mock_repo.upsert_node.call_args[0][1]["level"] == "expert"


@pytest.mark.anyio
async def test_upsert_skill_never_downgrades_level() -> None:
    """Regression test: a small/simple project that only used a skill at a
    lower level must NOT erase a previously-earned higher rating.
    """
    ingestion, mock_repo = _make_ingestion()
    mock_repo.get_node.return_value = {
        "id": "skill_python",
        "name": "Python",
        "category": "language",
        "level": "expert",
    }

    await ingestion._upsert_skill_preserving_existing(
        skill_id="skill_python", name="Python", category="language", level="beginner"
    )

    assert mock_repo.upsert_node.call_args[0][1]["level"] == "expert"


@pytest.mark.anyio
async def test_upsert_skill_category_still_preserved_from_first_classification() -> None:
    """Category, unlike level, is set once and never overwritten."""
    ingestion, mock_repo = _make_ingestion()
    mock_repo.get_node.return_value = {
        "id": "skill_python",
        "name": "Python",
        "category": "language",
        "level": "beginner",
    }

    await ingestion._upsert_skill_preserving_existing(
        skill_id="skill_python", name="Python", category="tool", level="advanced"
    )

    properties = mock_repo.upsert_node.call_args[0][1]
    assert properties["category"] == "language"
    assert properties["level"] == "advanced"


@pytest.mark.anyio
async def test_upsert_skill_equal_level_keeps_existing() -> None:
    ingestion, mock_repo = _make_ingestion()
    mock_repo.get_node.return_value = {
        "id": "skill_python",
        "name": "Python",
        "category": "language",
        "level": "intermediate",
    }

    await ingestion._upsert_skill_preserving_existing(
        skill_id="skill_python", name="Python", category="language", level="intermediate"
    )

    assert mock_repo.upsert_node.call_args[0][1]["level"] == "intermediate"


@pytest.mark.anyio
async def test_link_required_skills_does_not_pass_requires_level_to_skill_upsert() -> None:
    """Regression test: a job's REQUIRES-level ('expert') must never be
    forwarded as the Skill node's own `level` - that would conflate what the
    JOB expects with what the PERSON has demonstrated.
    """
    ingestion, mock_repo = _make_ingestion()
    mock_repo.get_node.return_value = None

    await ingestion._link_required_skills(
        job_id="job-1",
        skills=[{"name": "Rust", "level": "expert", "importance": "required"}],
    )

    skill_call = mock_repo.upsert_node.call_args_list[0]
    assert skill_call.args[0] == "Skill"
    assert skill_call.args[1]["level"] == "intermediate"

    rel_call = mock_repo.upsert_relationship.call_args_list[0]
    assert rel_call.kwargs["properties"] == {"level": "expert", "importance": "required"}


@pytest.mark.anyio
async def test_link_required_skills_accepts_plain_string_list_back_compat() -> None:
    """`upsert_job_offer` still passes plain skill names (no level/importance)."""
    ingestion, mock_repo = _make_ingestion()
    mock_repo.get_node.return_value = None

    await ingestion._link_required_skills(job_id="job-1", skills=["Go"])

    rel_call = mock_repo.upsert_relationship.call_args_list[0]
    assert rel_call.kwargs["properties"] is None


@pytest.mark.anyio
async def test_promote_job_llm_analysis_sets_offer_fields_and_requires_properties() -> None:
    """The promote-time LLM analysis call enriches the JobOffer node with
    seniority/experience years and writes per-skill level/importance onto
    REQUIRES - without ever bumping the Skill node's own level.
    """
    repo = MagicMock()
    repo.get_node = AsyncMock(side_effect=[None, None, None, None])
    repo.upsert_node = AsyncMock()
    repo.upsert_relationship = AsyncMock()

    embeddings = MagicMock()
    embeddings.embed_text = AsyncMock(return_value=[0.1, 0.2, 0.3])

    listing = {
        "id": "job-2",
        "title": "Senior Backend Engineer",
        "company": "Acme Corp",
        "description": "Looking for a senior engineer with 5+ years of Python and Kubernetes.",
        "required_skills": [],
        "url": "https://example.com/job/2",
        "source": "indeed",
        "scraped_at": "2026-01-01T00:00:00+00:00",
    }

    analysis_json = (
        '{"seniority": "senior", "min_experience_years": 5, "max_experience_years": null, '
        '"skills": [{"name": "Python", "level": "advanced", "importance": "required"}, '
        '{"name": "Kubernetes", "level": "intermediate", "importance": "preferred"}]}'
    )

    with (
        patch("app.kg.ingestion.create_company_enrichment_chain") as mock_company_factory,
        patch("app.kg.ingestion.create_job_analysis_chain") as mock_analysis_factory,
    ):
        mock_company_chain = AsyncMock()
        mock_company_chain.ainvoke.return_value = _llm_response('{"industry": "", "website": ""}')
        mock_company_factory.return_value = mock_company_chain

        mock_analysis_chain = AsyncMock()
        mock_analysis_chain.ainvoke.return_value = _llm_response(analysis_json)
        mock_analysis_factory.return_value = mock_analysis_chain

        ingestion = KGIngestion(kg_repository=repo, embeddings=embeddings, scrape_ttl_days=7)
        props, newly = await ingestion.promote_job(job_id="job-2", listing=listing)

    assert newly is True
    assert props["seniority"] == "senior"
    assert props["min_experience_years"] == 5
    assert props["max_experience_years"] is None
    assert set(props["required_skills"]) == {"Python", "Kubernetes"}

    requires_calls = [
        call
        for call in repo.upsert_relationship.await_args_list
        if call.kwargs.get("relationship_type") == "REQUIRES"
    ]
    by_skill = {call.kwargs["to_id"]: call.kwargs["properties"] for call in requires_calls}
    assert by_skill["skill_python"] == {"level": "advanced", "importance": "required"}
    assert by_skill["skill_kubernetes"] == {"level": "intermediate", "importance": "preferred"}

    skill_upserts = [
        call for call in repo.upsert_node.await_args_list if call.args[0] == "Skill"
    ]
    assert len(skill_upserts) == 2
    for call in skill_upserts:
        assert call.args[1]["level"] == "intermediate"


@pytest.mark.anyio
async def test_promote_job_falls_back_to_heuristic_seed_when_llm_analysis_fails() -> None:
    repo = MagicMock()
    repo.get_node = AsyncMock(side_effect=[None, None, None])
    repo.upsert_node = AsyncMock()
    repo.upsert_relationship = AsyncMock()

    embeddings = MagicMock()
    embeddings.embed_text = AsyncMock(return_value=[0.1, 0.2, 0.3])

    listing = {
        "id": "job-3",
        "title": "Junior Developer",
        "company": "Acme Corp",
        "description": "Entry level role, 1 year of experience with Python required.",
        "required_skills": ["Python"],
        "url": "https://example.com/job/3",
        "source": "indeed",
        "scraped_at": "2026-01-01T00:00:00+00:00",
    }

    with (
        patch("app.kg.ingestion.create_company_enrichment_chain") as mock_company_factory,
        patch("app.kg.ingestion.create_job_analysis_chain") as mock_analysis_factory,
        patch("app.kg.ingestion.asyncio.sleep", new=AsyncMock()),
    ):
        mock_company_chain = AsyncMock()
        mock_company_chain.ainvoke.return_value = _llm_response('{"industry": "", "website": ""}')
        mock_company_factory.return_value = mock_company_chain

        mock_analysis_chain = AsyncMock()
        mock_analysis_chain.ainvoke.side_effect = RuntimeError("llm down")
        mock_analysis_factory.return_value = mock_analysis_chain

        ingestion = KGIngestion(kg_repository=repo, embeddings=embeddings, scrape_ttl_days=7)
        props, newly = await ingestion.promote_job(job_id="job-3", listing=listing)

    assert mock_analysis_chain.ainvoke.await_count == 3

    assert newly is True
    assert props["seniority"] == "junior"
    assert props["required_skills"] == ["Python"]

    requires_calls = [
        call
        for call in repo.upsert_relationship.await_args_list
        if call.kwargs.get("relationship_type") == "REQUIRES"
    ]
    # Fallback REQUIRES.level derives from seniority when the LLM gave none.
    assert requires_calls[0].kwargs["properties"] == {
        "level": "beginner",
        "importance": "required",
    }


@pytest.mark.anyio
async def test_ingest_email_creates_node_and_received_edge() -> None:
    ingestion, mock_repo = _make_ingestion()
    mock_repo.query.return_value = []

    email_id = await ingestion.ingest_email(
        subject="Interview",
        sender="hr@acme.com",
        classification="career_related",
        summary="Invite",
        metadata={"received_at": "2026-04-15T12:00:00+00:00"},
        person_id="user_1",
        message_id="<new@mail.gmail.com>",
    )

    assert email_id
    email_upserts = [
        call
        for call in mock_repo.upsert_node.await_args_list
        if call.args[0] == "Email"
    ]
    assert email_upserts
    assert email_upserts[0].args[1]["classification"] == "career_related"
    assert email_upserts[0].args[1]["message_id"] == "<new@mail.gmail.com>"
    mock_repo.upsert_relationship.assert_awaited()


@pytest.mark.anyio
async def test_ingest_email_updates_existing_message_id() -> None:
    ingestion, mock_repo = _make_ingestion()
    mock_repo.query.return_value = [{"id": "email-existing"}]

    email_id = await ingestion.ingest_email(
        subject="Interview",
        sender="hr@acme.com",
        classification="career_related",
        summary="Invite",
        metadata={},
        person_id="user_1",
        message_id="<dup@mail.gmail.com>",
    )

    assert email_id == "email-existing"
    email_upserts = [
        call
        for call in mock_repo.upsert_node.await_args_list
        if call.args[0] == "Email"
    ]
    assert email_upserts[0].args[1]["id"] == "email-existing"
    received = [
        call
        for call in mock_repo.upsert_relationship.await_args_list
        if call.kwargs.get("relationship_type") == "RECEIVED"
        or (call.args and "RECEIVED" in call.args)
    ]
    assert received
