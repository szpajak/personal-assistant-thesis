from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.portfolio import ProjectCreate, ProjectUpdate, SkillDraft
from app.services.portfolio_service import PortfolioService


def _llm_response(content: str) -> AsyncMock:
    response = AsyncMock()
    response.content = content
    return response


@pytest.mark.anyio
async def test_create_project_enriches_skills_and_seniority() -> None:
    mock_repo = AsyncMock()
    mock_ingestion = AsyncMock()
    mock_ingestion.ingest_project.return_value = "proj_123"

    service = PortfolioService(kg_repository=mock_repo, kg_ingestion=mock_ingestion)

    project = ProjectCreate(
        title="Test Project",
        description="Built a distributed system that scaled to 1M users.",
        tech_stack=["Python", "Kafka"],
        start_date=date(2023, 1, 1),
    )

    enrichment_json = (
        '{"skills": ['
        '{"name": "Python", "canonical_name": "Python", "category": "language", "confidence": 1.0}, '
        '{"name": "Kafka", "canonical_name": "Apache Kafka", "category": "tool", "confidence": 1.0}'
        '], "seniority": "senior"}'
    )

    with patch(
        "app.services.portfolio_service.create_project_enrichment_chain"
    ) as mock_chain_factory:
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = _llm_response(enrichment_json)
        mock_chain_factory.return_value = mock_chain

        result = await service.create_project("user_1", project)

    assert result.id == "proj_123"
    assert result.title == "Test Project"
    assert result.seniority == "senior"
    assert {s.category for s in result.skills} == {"language", "tool"}

    mock_ingestion.ingest_project.assert_called_once()
    _, kwargs = mock_ingestion.ingest_project.call_args
    assert kwargs["metadata"]["seniority"] == "senior"
    assert kwargs["metadata"]["source"] == "form"
    assert len(kwargs["skills"]) == 2

    mock_repo.upsert_relationship.assert_called_once()


@pytest.mark.anyio
async def test_create_project_enrichment_failure_falls_back_to_tech_stack() -> None:
    mock_repo = AsyncMock()
    mock_ingestion = AsyncMock()
    mock_ingestion.ingest_project.return_value = "proj_456"

    service = PortfolioService(kg_repository=mock_repo, kg_ingestion=mock_ingestion)

    project = ProjectCreate(
        title="Fallback Project",
        description="Some description",
        tech_stack=["Go"],
        start_date=date(2023, 1, 1),
    )

    with patch(
        "app.services.portfolio_service.create_project_enrichment_chain"
    ) as mock_chain_factory:
        mock_chain = AsyncMock()
        mock_chain.ainvoke.side_effect = RuntimeError("LLM unavailable")
        mock_chain_factory.return_value = mock_chain

        result = await service.create_project("user_1", project)

    assert result.id == "proj_456"
    assert result.seniority is None
    # ingest_project still gets a usable structured skills list (default
    # category, "intermediate" level) even though the enrichment LLM failed.
    _, kwargs = mock_ingestion.ingest_project.call_args
    assert kwargs["tech_stack"] == ["Go"]
    assert kwargs["skills"] == [
        {
            "name": "Go",
            "canonical_name": None,
            "category": "technical",
            "level": "intermediate",
            "confidence": 1.0,
        }
    ]


@pytest.mark.anyio
async def test_create_project_enrichment_never_overrides_user_level() -> None:
    """Regression test: the user self-assesses each skill's level via the
    form. Even if the enrichment LLM ignores its instructions and tries to
    change a level, the service must enforce the user's original value.
    """
    mock_repo = AsyncMock()
    mock_ingestion = AsyncMock()
    mock_ingestion.ingest_project.return_value = "proj_levels"

    service = PortfolioService(kg_repository=mock_repo, kg_ingestion=mock_ingestion)

    project = ProjectCreate(
        title="Level Test Project",
        description="Used CI/CD pipelines to deploy the service automatically.",
        tech_stack=["Python"],
        start_date=date(2023, 1, 1),
        skills=[SkillDraft(name="Python", category="technical", level="expert", confidence=1.0)],
    )

    # The LLM (mis)behaves and returns a different level for the user-listed
    # skill, plus an additional inferred skill implied by the description.
    enrichment_json = (
        '{"skills": ['
        '{"name": "Python", "canonical_name": "Python", "category": "language", '
        '"level": "beginner", "confidence": 1.0}, '
        '{"name": "CI/CD", "canonical_name": "CI/CD", "category": "tool", '
        '"level": "advanced", "confidence": 0.7}'
        '], "seniority": "mid"}'
    )

    with patch(
        "app.services.portfolio_service.create_project_enrichment_chain"
    ) as mock_chain_factory:
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = _llm_response(enrichment_json)
        mock_chain_factory.return_value = mock_chain

        result = await service.create_project("user_1", project)

    skills_by_name = {s.name: s for s in result.skills}
    # User-set level survives despite the LLM trying to change it.
    assert skills_by_name["Python"].level == "expert"
    assert skills_by_name["Python"].category == "language"
    # A newly inferred skill (not in the user's list) keeps the LLM's
    # assessed level, since the user never set one for it.
    assert skills_by_name["CI/CD"].level == "advanced"

    _, kwargs = mock_ingestion.ingest_project.call_args
    ingested_by_name = {s["name"]: s for s in kwargs["skills"]}
    assert ingested_by_name["Python"]["level"] == "expert"
    assert ingested_by_name["CI/CD"]["level"] == "advanced"


@pytest.mark.anyio
async def test_create_project_skip_enrichment_uses_confirmed_draft() -> None:
    mock_repo = AsyncMock()
    mock_ingestion = AsyncMock()
    mock_ingestion.ingest_project.return_value = "proj_confirmed"

    service = PortfolioService(kg_repository=mock_repo, kg_ingestion=mock_ingestion)

    project = ProjectCreate(
        title="Confirmed Draft",
        description="Already extracted and reviewed by the user",
        tech_stack=["Rust"],
        start_date=date(2023, 1, 1),
        seniority="lead",
        skills=[
            SkillDraft(
                name="Rust", canonical_name="Rust", category="language", level="expert", confidence=0.9
            )
        ],
        skip_enrichment=True,
    )

    with patch(
        "app.services.portfolio_service.create_project_enrichment_chain"
    ) as mock_chain_factory:
        result = await service.create_project("user_1", project)

        mock_chain_factory.assert_not_called()

    assert result.id == "proj_confirmed"
    assert result.seniority == "lead"
    assert result.skills[0].level == "expert"
    _, kwargs = mock_ingestion.ingest_project.call_args
    assert kwargs["metadata"]["source"] == "upload"
    assert kwargs["skills"][0]["category"] == "language"
    assert kwargs["skills"][0]["level"] == "expert"


@pytest.mark.anyio
async def test_list_projects() -> None:
    mock_repo = AsyncMock()
    mock_repo.find_related_nodes.return_value = [
        {
            "id": "p1",
            "title": "Title 1",
            "description": "Desc 1",
            "tech_stack": ["JS"],
            "start_date": "2023-01-01",
            "seniority": "mid",
            "achievements": ["Shipped v1"],
        }
    ]
    mock_ingestion = AsyncMock()

    service = PortfolioService(kg_repository=mock_repo, kg_ingestion=mock_ingestion)

    result = await service.list_projects("user_1")

    assert len(result) == 1
    assert result[0].id == "p1"
    assert result[0].start_date == date(2023, 1, 1)
    assert result[0].seniority == "mid"
    assert result[0].achievements == ["Shipped v1"]


@pytest.mark.anyio
async def test_extract_project_drafts_single_project() -> None:
    mock_repo = AsyncMock()
    mock_ingestion = AsyncMock()

    service = PortfolioService(kg_repository=mock_repo, kg_ingestion=mock_ingestion)

    mock_parsed = {"title": "Resume", "text": "Parsed resume content", "metadata": {}}
    extraction_json = (
        "["
        '{"title": "Resume", "description": "Parsed resume content", '
        '"skills": [{"name": "Python", "canonical_name": "Python", "category": "language", '
        '"level": "advanced", "confidence": 0.9}], '
        '"start_date": "2023-01-01", "end_date": null, "achievements": ["Led team of 3"], "seniority": "senior"}'
        "]"
    )

    with (
        patch("app.services.portfolio_service.DocumentParser") as MockParser,
        patch(
            "app.services.portfolio_service.create_project_extraction_chain"
        ) as mock_chain_factory,
    ):
        instance = MockParser.return_value
        instance.parse_file = AsyncMock(return_value=mock_parsed)

        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = _llm_response(extraction_json)
        mock_chain_factory.return_value = mock_chain

        drafts = await service.extract_project_drafts("resume.pdf")

    assert len(drafts) == 1
    draft = drafts[0]
    assert draft.title == "Resume"
    assert draft.source == "upload"
    assert draft.seniority == "senior"
    assert draft.achievements == ["Led team of 3"]
    assert draft.skills[0].category == "language"
    assert draft.skills[0].level == "advanced"
    assert draft.tech_stack == ["Python"]
    # Extraction must never write to the KG - only the confirm step does.
    mock_ingestion.ingest_project.assert_not_called()
    mock_repo.upsert_node.assert_not_called()


@pytest.mark.anyio
async def test_extract_project_drafts_multiple_projects() -> None:
    mock_repo = AsyncMock()
    mock_ingestion = AsyncMock()

    service = PortfolioService(kg_repository=mock_repo, kg_ingestion=mock_ingestion)

    mock_parsed = {"title": "CV", "text": "Full CV with two projects", "metadata": {}}
    extraction_json = (
        "["
        '{"title": "Project A", "description": "First project", "skills": []}, '
        '{"title": "Project B", "description": "Second project", "skills": []}'
        "]"
    )

    with (
        patch("app.services.portfolio_service.DocumentParser") as MockParser,
        patch(
            "app.services.portfolio_service.create_project_extraction_chain"
        ) as mock_chain_factory,
    ):
        instance = MockParser.return_value
        instance.parse_file = AsyncMock(return_value=mock_parsed)

        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = _llm_response(extraction_json)
        mock_chain_factory.return_value = mock_chain

        drafts = await service.extract_project_drafts("cv.pdf")

    assert len(drafts) == 2
    assert [d.title for d in drafts] == ["Project A", "Project B"]
    mock_ingestion.ingest_project.assert_not_called()


@pytest.mark.anyio
async def test_extract_project_drafts_coerces_unrecognized_skill_category() -> None:
    """Regression test: an LLM-returned category outside our controlled
    vocabulary (e.g. "library") must be coerced, not raise a validation
    error that aborts the whole upload.
    """
    mock_repo = AsyncMock()
    mock_ingestion = AsyncMock()

    service = PortfolioService(kg_repository=mock_repo, kg_ingestion=mock_ingestion)

    mock_parsed = {"title": "Resume", "text": "Parsed resume content", "metadata": {}}
    extraction_json = (
        "["
        '{"title": "Resume", "description": "Parsed resume content", '
        '"skills": [{"name": "Requests", "canonical_name": "Requests", '
        '"category": "library", "confidence": 0.9}], '
        '"seniority": "expert"}'
        "]"
    )

    with (
        patch("app.services.portfolio_service.DocumentParser") as MockParser,
        patch(
            "app.services.portfolio_service.create_project_extraction_chain"
        ) as mock_chain_factory,
    ):
        instance = MockParser.return_value
        instance.parse_file = AsyncMock(return_value=mock_parsed)

        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = _llm_response(extraction_json)
        mock_chain_factory.return_value = mock_chain

        drafts = await service.extract_project_drafts("resume.pdf")

    assert len(drafts) == 1
    # "library" is not in our controlled vocabulary -> coerced to "framework".
    assert drafts[0].skills[0].category == "framework"
    # "expert" is not a recognized seniority level -> coerced to None rather
    # than raising.
    assert drafts[0].seniority is None


@pytest.mark.anyio
async def test_extract_project_drafts_coerces_unrecognized_skill_level() -> None:
    """Regression test: an LLM-returned skill level outside our controlled
    vocabulary (e.g. "novice") must be coerced to the closest match rather
    than raising.
    """
    mock_repo = AsyncMock()
    mock_ingestion = AsyncMock()

    service = PortfolioService(kg_repository=mock_repo, kg_ingestion=mock_ingestion)

    mock_parsed = {"title": "Resume", "text": "Parsed resume content", "metadata": {}}
    extraction_json = (
        "["
        '{"title": "Resume", "description": "Parsed resume content", '
        '"skills": [{"name": "SQL", "canonical_name": "SQL", "category": "language", '
        '"level": "novice", "confidence": 0.9}]}'
        "]"
    )

    with (
        patch("app.services.portfolio_service.DocumentParser") as MockParser,
        patch(
            "app.services.portfolio_service.create_project_extraction_chain"
        ) as mock_chain_factory,
    ):
        instance = MockParser.return_value
        instance.parse_file = AsyncMock(return_value=mock_parsed)

        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = _llm_response(extraction_json)
        mock_chain_factory.return_value = mock_chain

        drafts = await service.extract_project_drafts("resume.pdf")

    assert len(drafts) == 1
    # "novice" is a known synonym for "beginner".
    assert drafts[0].skills[0].level == "beginner"


@pytest.mark.anyio
async def test_extract_project_drafts_malformed_llm_output_falls_back() -> None:
    mock_repo = AsyncMock()
    mock_ingestion = AsyncMock()

    service = PortfolioService(kg_repository=mock_repo, kg_ingestion=mock_ingestion)

    mock_parsed = {"title": "Resume", "text": "Parsed resume content", "metadata": {}}

    with (
        patch("app.services.portfolio_service.DocumentParser") as MockParser,
        patch(
            "app.services.portfolio_service.create_project_extraction_chain"
        ) as mock_chain_factory,
    ):
        instance = MockParser.return_value
        instance.parse_file = AsyncMock(return_value=mock_parsed)

        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = _llm_response("not valid json at all")
        mock_chain_factory.return_value = mock_chain

        drafts = await service.extract_project_drafts("resume.pdf")

    assert len(drafts) == 1
    assert drafts[0].title == "Resume"
    assert drafts[0].source == "upload"


@pytest.mark.anyio
async def test_create_finished_project_grants_has_skill() -> None:
    mock_repo = AsyncMock()
    mock_ingestion = AsyncMock()
    mock_ingestion.ingest_project.return_value = "proj_finished"
    mock_repo.ensure_has_skill_for_finished_projects = AsyncMock(return_value=2)

    service = PortfolioService(kg_repository=mock_repo, kg_ingestion=mock_ingestion)

    project = ProjectCreate(
        title="Shipped App",
        description="Done.",
        tech_stack=["Python", "Docker"],
        start_date=date(2023, 1, 1),
        status="finished",
        skip_enrichment=True,
        skills=[
            SkillDraft(name="Python", level="advanced"),
            SkillDraft(name="Docker", level="intermediate"),
        ],
    )

    await service.create_project("user_1", project)

    mock_repo.ensure_has_skill_for_finished_projects.assert_awaited_once_with(
        "user_1", project_id="proj_finished"
    )


@pytest.mark.anyio
async def test_create_planned_project_does_not_grant_has_skill() -> None:
    mock_repo = AsyncMock()
    mock_ingestion = AsyncMock()
    mock_ingestion.ingest_project.return_value = "proj_planned"
    mock_repo.ensure_has_skill_for_finished_projects = AsyncMock(return_value=0)

    service = PortfolioService(kg_repository=mock_repo, kg_ingestion=mock_ingestion)

    project = ProjectCreate(
        title="Idea",
        description="Not done yet.",
        tech_stack=["Rust"],
        start_date=date(2023, 1, 1),
        status="planned",
        skip_enrichment=True,
    )

    await service.create_project("user_1", project)

    mock_repo.ensure_has_skill_for_finished_projects.assert_not_called()


@pytest.mark.anyio
async def test_update_project_to_finished_grants_has_skill() -> None:
    mock_repo = AsyncMock()
    mock_ingestion = AsyncMock()
    mock_repo.get_node.return_value = {
        "id": "proj_1",
        "title": "App",
        "description": "desc",
        "tech_stack": ["Python"],
        "start_date": "2023-01-01",
        "status": "in_progress",
    }
    mock_repo.find_related_nodes.return_value = [{"id": "proj_1"}]
    mock_repo.ensure_has_skill_for_finished_projects = AsyncMock(return_value=1)

    service = PortfolioService(kg_repository=mock_repo, kg_ingestion=mock_ingestion)

    result = await service.update_project(
        "user_1",
        "proj_1",
        ProjectUpdate(status="finished"),
    )

    assert result.status == "finished"
    mock_repo.ensure_has_skill_for_finished_projects.assert_awaited_once_with(
        "user_1", project_id="proj_1"
    )


@pytest.mark.anyio
async def test_update_project_staying_in_progress_skips_has_skill() -> None:
    mock_repo = AsyncMock()
    mock_ingestion = AsyncMock()
    mock_repo.get_node.return_value = {
        "id": "proj_1",
        "title": "App",
        "description": "desc",
        "tech_stack": ["Python"],
        "start_date": "2023-01-01",
        "status": "in_progress",
    }
    mock_repo.find_related_nodes.return_value = [{"id": "proj_1"}]
    mock_repo.ensure_has_skill_for_finished_projects = AsyncMock(return_value=0)

    service = PortfolioService(kg_repository=mock_repo, kg_ingestion=mock_ingestion)

    await service.update_project(
        "user_1",
        "proj_1",
        ProjectUpdate(title="Renamed"),
    )

    mock_repo.ensure_has_skill_for_finished_projects.assert_not_called()
