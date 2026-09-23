from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from .jobs import JobOfferRead


class ApplicationCreate(BaseModel):
    job_offer_id: str
    status: str
    applied_at: datetime | None = None
    notes: str | None = None


class ApplicationRead(ApplicationCreate):
    id: str
    job_offer: JobOfferRead | None = None


class ApplicationUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None
