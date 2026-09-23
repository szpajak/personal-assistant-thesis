from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.kg.ingestion import KGIngestion
from app.kg.repository import KGRepository
from app.pipelines.email_pipeline import EmailPipeline


@pytest.fixture
def mock_kg_ingestion() -> AsyncMock:
    return AsyncMock(spec=KGIngestion)


@pytest.fixture
def email_pipeline(
    kg_repository: KGRepository, mock_kg_ingestion: AsyncMock
) -> EmailPipeline:
    return EmailPipeline(kg_repository=kg_repository, kg_ingestion=mock_kg_ingestion)


@pytest.mark.asyncio
async def test_email_pipeline_run(
    email_pipeline: EmailPipeline, mock_kg_ingestion: AsyncMock
) -> None:
    # Arrange
    raw_emails = [
        {"subject": "Job Offer", "body": "We want you!", "sender": "hr@tech.com"}
    ]
    mock_kg_ingestion.ingest_email.return_value = "email-1"

    mock_response = AIMessage(
        content=(
            '{"classification": "job_offer", "summary": "Got a job!", '
            '"action_required": true, "entity_name": "Tech Corp", '
            '"application_stage": "none"}'
        )
    )

    with patch("langchain_deepseek.ChatDeepSeek.ainvoke", return_value=mock_response):
        # Act
        result = await email_pipeline.run(raw_emails, person_id="user_1")

    # Assert
    assert len(result) == 1
    assert result[0]["analysis"]["classification"] == "job_offer"
    assert result[0]["kg_id"] == "email-1"
    mock_kg_ingestion.ingest_email.assert_called_once_with(
        subject="Job Offer",
        sender="hr@tech.com",
        classification="job_offer",
        summary="Got a job!",
        metadata={"received_at": None},
        person_id="user_1",
        entity_name="Tech Corp",
        message_id=None,
    )


@pytest.mark.asyncio
async def test_email_pipeline_defaults_to_primary_person(
    email_pipeline: EmailPipeline, mock_kg_ingestion: AsyncMock
) -> None:
    """Background polling has no auth context, so the pipeline must fall back
    to the configured primary person instead of leaving emails ownerless.
    """
    from app.config import settings

    raw_emails = [{"subject": "Hi", "body": "Hello", "sender": "a@b.com"}]
    mock_kg_ingestion.ingest_email.return_value = "email-2"

    mock_response = AIMessage(
        content=(
            '{"classification": "other", "summary": "n/a", '
            '"action_required": false, "entity_name": "", "application_stage": "none"}'
        )
    )

    with patch("langchain_deepseek.ChatDeepSeek.ainvoke", return_value=mock_response):
        await email_pipeline.run(raw_emails)

    _, kwargs = mock_kg_ingestion.ingest_email.call_args
    assert kwargs["person_id"] == settings.primary_person_id
