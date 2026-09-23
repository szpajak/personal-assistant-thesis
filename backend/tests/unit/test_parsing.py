from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.utils.parsing import DocumentParser


@pytest.mark.anyio
async def test_parse_file_success() -> None:
    parser = DocumentParser()

    # Mock partition function
    mock_elements = [
        MagicMock(__str__=lambda x: "Hello"),
        MagicMock(__str__=lambda x: "World"),
    ]

    with patch("app.utils.parsing.partition", return_value=mock_elements):
        result = await parser.parse_file("test_docs/resume.pdf")

        assert result["text"] == "Hello\nWorld"
        assert result["title"] == "resume.pdf"
        assert result["metadata"]["file_type"] == "pdf"
        assert result["metadata"]["element_count"] == 2


@pytest.mark.anyio
async def test_extract_email_text() -> None:
    parser = DocumentParser()
    email_content = {
        "subject": "Interview Request",
        "body": "Hi, we want to interview you.",
        "sender": "hr@company.com",
        "received_at": "2024-05-10T10:00:00",
    }

    result = await parser.extract_email_text(email_content)

    assert result["subject"] == email_content["subject"]
    assert result["body"] == email_content["body"]
    assert result["sender"] == email_content["sender"]
    assert result["received_at"] == email_content["received_at"]


@pytest.mark.anyio
async def test_parse_docx_uses_python_docx() -> None:
    parser = DocumentParser()
    mock_document = MagicMock()
    mock_document.paragraphs = [
        MagicMock(text="Project title"),
        MagicMock(text=""),
        MagicMock(text="Built APIs with FastAPI"),
    ]

    with patch("docx.Document", return_value=mock_document):
        result = await parser.parse_file("/tmp/portfolio.docx")

    assert "Project title" in result["text"]
    assert "FastAPI" in result["text"]
    assert result["metadata"]["parser"] == "python-docx"
    assert result["metadata"]["file_type"] == "docx"


@pytest.mark.anyio
async def test_parse_file_failure() -> None:
    parser = DocumentParser()

    with patch("app.utils.parsing.partition", side_effect=Exception("Parsing error")):
        with pytest.raises(Exception) as excinfo:
            await parser.parse_file("test_docs/bad.pdf")

        assert "Parsing error" in str(excinfo.value)
