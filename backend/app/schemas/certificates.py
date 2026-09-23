from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class CertificateCreate(BaseModel):
    title: str
    issuer: str
    issued_at: str | None = None
    document_url: str = ""
    validated_skills: List[str] = Field(default_factory=list)


class CertificateRead(CertificateCreate):
    id: str


class CertificateDraft(BaseModel):
    """LLM-extracted draft for a certificate, pending user review/confirmation.

    Mirrors the portfolio ``ProjectDraft`` pattern: extraction never writes to
    the KG directly - the frontend shows this for edit/confirm, then submits
    it as a ``CertificateCreate`` via the normal create endpoint.
    """

    title: str
    issuer: str = ""
    issued_at: str | None = None
    validated_skills: List[str] = Field(default_factory=list)


class CertificateExtractResponse(BaseModel):
    drafts: List[CertificateDraft] = Field(default_factory=list)
