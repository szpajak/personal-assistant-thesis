"""Service for email processing, classification, and IMAP integration."""

from __future__ import annotations

import json
import logging
import re
import ssl
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parsedate_to_datetime
from typing import Any

from imapclient import IMAPClient

from ..config import settings
from ..kg.chains import create_email_classification_chain
from ..kg.ingestion import KGIngestion
from ..pipelines.email_pipeline import EmailPipeline

logger = logging.getLogger(__name__)

# One poll handles the newest unseen messages. Older unread mail stays
# unseen and is picked up on the next scheduled or manual sync.
_UNSEEN_BATCH = 50


class EmailService:
    """Process and classify emails from IMAP inbox."""

    def __init__(
        self,
        kg_ingestion: KGIngestion,
        email_pipeline: EmailPipeline,
    ) -> None:
        """Initialize email service.

        Args:
            kg_ingestion: KG ingestion service
            email_pipeline: LangGraph pipeline for email processing

        """
        self.kg_ingestion = kg_ingestion
        self.email_pipeline = email_pipeline

    @staticmethod
    def _build_ssl_context() -> ssl.SSLContext:
        """Build the TLS context used for the IMAP connection.

        Uses strict certificate verification by default. A custom CA bundle can
        be supplied via ``IMAP_CA_FILE`` for self-signed servers, or verification
        can be disabled entirely with ``IMAP_VERIFY_SSL=false`` (trusted networks
        only).
        """
        if settings.imap_ca_file:
            context = ssl.create_default_context(cafile=settings.imap_ca_file)
        else:
            context = ssl.create_default_context()
        if not settings.imap_verify_ssl:
            logger.warning(
                "IMAP TLS certificate verification is disabled "
                "(IMAP_VERIFY_SSL=false). Use only on trusted networks."
            )
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        return context

    @staticmethod
    def _decode_header_value(value: str | None) -> str:
        """Decode an RFC 2047 encoded header into a plain Unicode string."""
        if not value:
            return ""
        try:
            return str(make_header(decode_header(value)))
        except Exception:
            return value

    @staticmethod
    def _extract_body(msg: Message) -> str:
        """Extract a readable plaintext body from a (possibly multipart) message.

        Prefers a substantial ``text/plain`` part. A short plain stub yields
        to stripped HTML, which is where many applicant-tracking messages
        put the status. Attachments are skipped.
        """
        plain_parts: list[str] = []
        html_parts: list[str] = []

        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get_content_disposition() == "attachment":
                continue

            content_type = part.get_content_type()
            try:
                payload = part.get_payload(decode=True)
            except Exception:
                continue
            if not isinstance(payload, (bytes, bytearray)):
                continue

            charset = part.get_content_charset() or "utf-8"
            text = bytes(payload).decode(charset, errors="replace")

            if content_type == "text/plain":
                plain_parts.append(text)
            elif content_type == "text/html":
                html_parts.append(text)

        plain = "\n".join(plain_parts).strip()
        html_text = ""
        if html_parts:
            stripped = re.sub(
                r"(?is)<(script|style).*?>.*?</\1>", " ", "\n".join(html_parts)
            )
            stripped = re.sub(r"(?s)<[^>]+>", " ", stripped)
            html_text = re.sub(r"\s+", " ", stripped).strip()

        if plain and html_text:
            # ATS mail often attaches a one-line plain alternative
            # ("View this email in your browser") and puts the status in HTML.
            if len(plain) < 40 and len(html_text) > len(plain):
                return html_text
            return plain
        if plain:
            return plain

        if html_text:
            return html_text

        # Non-multipart message whose payload is already a string.
        payload = msg.get_payload(decode=True)
        if isinstance(payload, (bytes, bytearray)):
            charset = msg.get_content_charset() or "utf-8"
            return bytes(payload).decode(charset, errors="replace").strip()
        if isinstance(payload, str):
            return payload.strip()
        return ""

    @classmethod
    def _parse_raw_message(cls, raw_bytes: bytes) -> dict[str, Any]:
        """Parse RFC822 bytes fetched via IMAP into subject/body/sender."""
        msg = message_from_bytes(raw_bytes)
        subject = cls._decode_header_value(msg.get("Subject"))
        sender = cls._decode_header_value(msg.get("From"))
        body = cls._extract_body(msg)
        message_id = cls._decode_header_value(
            msg.get("Message-ID") or msg.get("Message-Id")
        ).strip()

        received_at = None
        date_header = msg.get("Date")
        if date_header:
            try:
                received_at = parsedate_to_datetime(date_header).isoformat()
            except (TypeError, ValueError, IndexError, OverflowError):
                received_at = None

        return {
            "subject": subject,
            "body": body,
            "sender": sender,
            "received_at": received_at,
            "message_id": message_id,
        }

    async def _lookup_ingested_email(self, message_id: str) -> dict[str, Any] | None:
        """Return existing Email node metadata for this Message-ID, if any."""
        try:
            rows = await self.kg_ingestion.kg_repository.query(
                """
                MATCH (e:Email {message_id: $message_id})
                OPTIONAL MATCH (p:Person)-[:RECEIVED]->(e)
                RETURN e.id AS id,
                       e.classification AS classification,
                       collect(p.id) AS person_ids
                LIMIT 1
                """,
                {"message_id": message_id},
            )
            if not rows or not rows[0].get("id"):
                return None
            person_ids = [str(pid) for pid in (rows[0].get("person_ids") or []) if pid]
            return {
                "id": str(rows[0]["id"]),
                "classification": rows[0].get("classification"),
                "person_ids": person_ids,
            }
        except Exception as exc:
            logger.warning("Message-ID lookup failed: %s", exc)
            return None

    @staticmethod
    def _email_fully_processed(existing: dict[str, Any], person_id: str | None) -> bool:
        """True when the node is classified and owned by ``person_id``."""
        classification = str(existing.get("classification") or "").strip()
        if not classification:
            return False
        if not person_id:
            return True
        return person_id in (existing.get("person_ids") or [])

    @staticmethod
    def _mark_seen(client: IMAPClient, imap_ids: list[Any]) -> None:
        if not imap_ids:
            return
        try:
            client.add_flags(imap_ids, ["\\Seen"])
        except Exception as exc:
            logger.warning("Failed to mark IMAP messages as Seen: %s", exc)

    async def poll_inbox(self, person_id: str | None = None) -> list[dict[str, Any]]:
        """Poll IMAP inbox for new emails and classify them.

        Args:
            person_id: Owning Person for RECEIVED / application-matching
                edges. Defaults (inside the pipeline) to the configured
                primary person when omitted, since scheduled polls have no
                authenticated request context.

        Returns:
            List of processed emails with classifications

        """
        owner = person_id or settings.primary_person_id
        try:
            await self.email_pipeline.reconcile_application_emails(owner)
        except Exception as exc:
            logger.warning("Could not repair application email links: %s", exc)

        try:
            # Connect to IMAP server
            client = IMAPClient(
                settings.imap_host,
                port=settings.imap_port,
                ssl=True,
                ssl_context=self._build_ssl_context(),
            )
            client.login(settings.imap_user, settings.imap_password)

            # Select inbox
            client.select_folder("INBOX")

            # Search for unseen emails
            email_ids = client.search("UNSEEN")

            raw_emails: list[dict[str, Any]] = []
            complete_imap_ids: list[Any] = []
            pending_imap_ids: list[Any] = []

            # Highest IMAP ids are the newest messages on typical servers.
            batch = list(email_ids)[-_UNSEEN_BATCH:]
            for email_id in batch:
                try:
                    # BODY.PEEK[] returns the full RFC822 message without
                    # setting \\Seen, so a failed classify/ingest still leaves
                    # the message eligible for the next UNSEEN poll. IMAPClient
                    # still exposes the payload under the BODY[] response key.
                    fetch_data = client.fetch([email_id], ["BODY.PEEK[]"])
                    email_data = fetch_data[email_id]
                    raw_bytes = (
                        email_data.get(b"BODY[]")
                        or email_data.get(b"BODY.PEEK[]")
                        or email_data.get(b"RFC822")
                    )
                    if not raw_bytes:
                        logger.error(
                            "IMAP fetch for %s returned no BODY[]/RFC822 payload "
                            "(keys=%s)",
                            email_id,
                            list(email_data.keys()),
                        )
                        continue

                    parsed = self._parse_raw_message(raw_bytes)
                    if not parsed["subject"] and not parsed["body"]:
                        logger.warning(
                            "Skipping email %s: empty subject and body after parse",
                            email_id,
                        )
                        continue

                    message_id = str(parsed.get("message_id") or "").strip()
                    if message_id:
                        existing = await self._lookup_ingested_email(message_id)
                        if existing and self._email_fully_processed(
                            existing, person_id
                        ):
                            logger.info(
                                "Skipping already-ingested Message-ID %s", message_id
                            )
                            complete_imap_ids.append(email_id)
                            continue

                    raw_emails.append(
                        {
                            "id": str(email_id),
                            **parsed,
                        }
                    )
                    pending_imap_ids.append(email_id)

                except Exception as e:
                    logger.error(f"Failed to fetch email {email_id}: {e}")

            self._mark_seen(client, complete_imap_ids)

            if not raw_emails:
                client.logout()
                return []

            # Use LangGraph pipeline for processing and ingestion
            processed_emails = await self.email_pipeline.run(
                raw_emails, person_id=person_id
            )
            self._mark_seen(client, pending_imap_ids)

            client.logout()
            logger.info(f"Processed {len(processed_emails)} emails using pipeline")
            return processed_emails

        except Exception as e:
            # Re-raise so the Celery task is marked as failed instead of
            # silently reporting success on a broken connection/login.
            logger.error(f"Failed to poll inbox: {e}")
            raise

    async def classify_email(
        self,
        subject: str,
        body: str,
    ) -> dict[str, Any]:
        """Classify an email using LLM.

        Args:
            subject: Email subject
            body: Email body

        Returns:
            Classification result with category and summary

        """
        try:
            chain = create_email_classification_chain()
            response = await chain.ainvoke({"subject": subject, "body": body})

            try:
                classification_data = json.loads(str(response.content))
                return dict(classification_data)
            except json.JSONDecodeError:
                logger.warning("Failed to parse LLM classification response")
                return {
                    "classification": "other",
                    "summary": subject[:100],
                    "action_required": False,
                    "entity_name": "",
                }

        except Exception as e:
            logger.error(f"Failed to classify email: {e}")
            return {
                "classification": "other",
                "summary": subject[:100],
                "action_required": False,
                "entity_name": "",
            }
