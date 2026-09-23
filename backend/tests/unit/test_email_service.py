from __future__ import annotations

import json
from email.message import EmailMessage
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.email_service import EmailService


def _build_rfc822(
    *,
    subject: str = "Test",
    sender: str = "sender@test.com",
    body: str = "Hello world",
    html: str | None = None,
    message_id: str | None = None,
) -> bytes:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["Date"] = "Mon, 10 Aug 2026 10:00:00 +0000"
    if message_id:
        msg["Message-ID"] = message_id
    if html is not None:
        msg.set_content(body)
        msg.add_alternative(html, subtype="html")
    else:
        msg.set_content(body)
    return msg.as_bytes()


@pytest.mark.anyio
async def test_classify_email_success() -> None:
    mock_ingestion = AsyncMock()
    mock_pipeline = AsyncMock()
    service = EmailService(kg_ingestion=mock_ingestion, email_pipeline=mock_pipeline)

    mock_response = MagicMock()
    mock_response.content = json.dumps(
        {
            "classification": "job_offer",
            "summary": "Software Engineer offer",
            "action_required": True,
            "entity_name": "Google",
        }
    )

    with patch(
        "app.services.email_service.create_email_classification_chain"
    ) as mock_create_chain:
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = mock_response
        mock_create_chain.return_value = mock_chain

        result = await service.classify_email("Job Offer", "We want to hire you.")

        assert result["classification"] == "job_offer"
        assert result["entity_name"] == "Google"


@pytest.mark.anyio
async def test_poll_inbox_success() -> None:
    mock_ingestion = AsyncMock()
    mock_pipeline = AsyncMock()
    mock_pipeline.run.return_value = [{"id": "1", "classification": "job_offer"}]

    service = EmailService(kg_ingestion=mock_ingestion, email_pipeline=mock_pipeline)

    with patch("app.services.email_service.IMAPClient") as MockIMAP:
        client_instance = MockIMAP.return_value
        client_instance.search.return_value = [1]
        # Real IMAPClient shape for fetch(["BODY[]"]): raw RFC822 under b"BODY[]".
        client_instance.fetch.return_value = {
            1: {b"BODY[]": _build_rfc822(subject="Test", body="Hello world")}
        }

        result = await service.poll_inbox()

        assert len(result) == 1
        assert result[0]["classification"] == "job_offer"
        assert client_instance.login.called
        assert client_instance.select_folder.called
        assert mock_pipeline.run.called
        client_instance.add_flags.assert_called()

        raw_emails = mock_pipeline.run.await_args.args[0]
        assert raw_emails[0]["subject"] == "Test"
        assert "Hello world" in raw_emails[0]["body"]
        assert raw_emails[0]["sender"] == "sender@test.com"
        assert raw_emails[0]["received_at"] is not None


def test_parse_raw_message_plain() -> None:
    parsed = EmailService._parse_raw_message(
        _build_rfc822(
            subject="Interview invite",
            sender="recruiter@acme.com",
            body="Please join us Tuesday.",
        )
    )
    assert parsed["subject"] == "Interview invite"
    assert parsed["sender"] == "recruiter@acme.com"
    assert "Please join us Tuesday." in parsed["body"]
    assert parsed["received_at"] is not None


def test_parse_raw_message_multipart_prefers_plain() -> None:
    parsed = EmailService._parse_raw_message(
        _build_rfc822(
            subject="Offer",
            body="Plain offer text that is long enough to be the real message body.",
            html="<html><body><b>HTML offer</b></body></html>",
        )
    )
    assert "Plain offer text" in parsed["body"]
    assert "HTML offer" not in parsed["body"]
    assert "<b>" not in parsed["body"]


def test_parse_raw_message_short_plain_stub_uses_html() -> None:
    parsed = EmailService._parse_raw_message(
        _build_rfc822(
            subject="Interview",
            body="View in browser",
            html=(
                "<html><body><p>We would like to invite you to interview.</p></body></html>"
            ),
        )
    )
    assert "invite you to interview" in parsed["body"]


def test_parse_raw_message_html_only_strips_tags() -> None:
    msg = EmailMessage()
    msg["Subject"] = "HTML only"
    msg["From"] = "hr@corp.com"
    msg.set_content("<p>We would like to <b>hire</b> you.</p>", subtype="html")

    parsed = EmailService._parse_raw_message(msg.as_bytes())
    assert parsed["subject"] == "HTML only"
    assert "hire" in parsed["body"]
    assert "<b>" not in parsed["body"]


@pytest.mark.anyio
async def test_poll_inbox_skips_complete_email_and_marks_seen() -> None:
    mock_ingestion = AsyncMock()
    mock_ingestion.kg_repository.query.return_value = [
        {
            "id": "email-1",
            "classification": "other",
            "person_ids": ["user_1"],
        }
    ]
    mock_pipeline = AsyncMock()
    service = EmailService(kg_ingestion=mock_ingestion, email_pipeline=mock_pipeline)

    with patch("app.services.email_service.IMAPClient") as MockIMAP:
        client_instance = MockIMAP.return_value
        client_instance.search.return_value = [1]
        client_instance.fetch.return_value = {
            1: {b"BODY[]": _build_rfc822(message_id="<already@mail.gmail.com>")}
        }

        result = await service.poll_inbox(person_id="user_1")

    assert result == []
    mock_pipeline.run.assert_not_called()
    client_instance.add_flags.assert_called_once_with([1], ["\\Seen"])


@pytest.mark.anyio
async def test_poll_inbox_reprocesses_email_owned_by_wrong_person() -> None:
    mock_ingestion = AsyncMock()
    mock_ingestion.kg_repository.query.return_value = [
        {
            "id": "email-1",
            "classification": "career_related",
            "person_ids": ["u1"],
        }
    ]
    mock_pipeline = AsyncMock()
    mock_pipeline.run.return_value = [{"id": "1", "classification": "career_related"}]
    service = EmailService(kg_ingestion=mock_ingestion, email_pipeline=mock_pipeline)

    with patch("app.services.email_service.IMAPClient") as MockIMAP:
        client_instance = MockIMAP.return_value
        client_instance.search.return_value = [1]
        client_instance.fetch.return_value = {
            1: {b"BODY[]": _build_rfc822(message_id="<stuck@mail.gmail.com>")}
        }

        result = await service.poll_inbox(person_id="user_1")

    assert len(result) == 1
    mock_pipeline.run.assert_called_once()
    client_instance.add_flags.assert_called_once_with([1], ["\\Seen"])


def test_email_fully_processed_requires_owner_and_classification() -> None:
    existing = {"classification": "other", "person_ids": ["u1"]}
    assert EmailService._email_fully_processed(existing, "user_1") is False
    assert EmailService._email_fully_processed(existing, "u1") is True
    assert (
        EmailService._email_fully_processed(
            {"classification": "", "person_ids": ["user_1"]}, "user_1"
        )
        is False
    )
