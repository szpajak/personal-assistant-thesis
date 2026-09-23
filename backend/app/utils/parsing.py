"""Document parsing utilities for extracting text from various formats."""

from __future__ import annotations

import logging
import os
from typing import Any

from unstructured.partition.auto import partition

logger = logging.getLogger(__name__)

# Shared backstop for any parsed-document text sent to an LLM (CV/portfolio
# project/certificate extraction). No real CV, certificate, or project
# writeup comes anywhere close to this - it exists purely to bound a
# corrupted parse (e.g. ``unstructured`` emitting a huge whitespace-repeated
# blob from a malformed PDF), not to ration a normal document.
DOCUMENT_MAX_CHARS = 20000


def truncate_document_text(text: str, max_chars: int = DOCUMENT_MAX_CHARS) -> str:
    """Truncate parsed document text before handing it to an LLM chain."""
    stripped = (text or "").strip()
    if len(stripped) <= max_chars:
        return stripped
    return stripped[:max_chars].rstrip() + "…"


class DocumentParser:
    """Parse documents (PDF, DOCX, TXT) and extract structured content."""

    async def parse_file(self, path: str) -> dict[str, Any]:
        """Parse a document file and extract text.

        Args:
            path: File path to parse

        Returns:
            Dictionary with 'text', 'title', and 'metadata' keys

        """
        file_type = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        filename = os.path.basename(path)

        try:
            if file_type == "docx":
                return self._parse_docx(path=path, filename=filename)

            elements = partition(filename=path)
            text_parts = [str(element) for element in elements]
            text = "\n".join(text_parts)

            return {
                "text": text,
                "title": filename,
                "metadata": {
                    "file_type": file_type,
                    "source_path": path,
                    "element_count": len(elements),
                    "parser": "unstructured",
                },
            }

        except Exception as e:
            logger.error(f"Failed to parse document {path}: {e}")
            raise

    def _parse_docx(self, path: str, filename: str) -> dict[str, Any]:
        """Parse DOCX via python-docx without NLTK/unstructured dependencies."""
        from docx import Document

        document = Document(path)
        paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs]
        text = "\n".join(paragraph for paragraph in paragraphs if paragraph)

        return {
            "text": text,
            "title": filename,
            "metadata": {
                "file_type": "docx",
                "source_path": path,
                "element_count": len(
                    [paragraph for paragraph in paragraphs if paragraph]
                ),
                "parser": "python-docx",
            },
        }

    async def extract_email_text(
        self,
        email_content: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract structured text from email content.

        Args:
            email_content: Email dict with subject, body, sender

        Returns:
            Extracted email data

        """
        return {
            "subject": email_content.get("subject", ""),
            "body": email_content.get("body", ""),
            "sender": email_content.get("sender", ""),
            "received_at": email_content.get("received_at"),
        }
