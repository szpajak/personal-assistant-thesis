from __future__ import annotations

from pydantic import BaseModel


class EmailRead(BaseModel):
    id: str
    subject: str = ""
    sender: str = ""
    received_at: str | None = None
    summary: str | None = None
    classification: str | None = None
