"""Schemas for career-chronology entities: Employment, Education, TargetRole."""

from __future__ import annotations

from datetime import date
from typing import List

from pydantic import BaseModel, Field


class EmploymentCreate(BaseModel):
    title: str
    company: str
    start_date: date
    end_date: date | None = None
    description: str = ""
    achievements: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)


class EmploymentRead(EmploymentCreate):
    id: str


class EmploymentUpdate(BaseModel):
    title: str | None = None
    company: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None
    achievements: List[str] | None = None
    skills: List[str] | None = None


class EmploymentDraft(BaseModel):
    """LLM-extracted draft, pending user review/confirmation before create."""

    title: str
    company: str
    start_date: date | None = None
    end_date: date | None = None
    description: str = ""
    achievements: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)


class EducationCreate(BaseModel):
    institution: str
    degree: str
    field_of_study: str = ""
    start_date: date
    end_date: date | None = None
    description: str = ""


class EducationRead(EducationCreate):
    id: str


class EducationUpdate(BaseModel):
    institution: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None


class EducationDraft(BaseModel):
    """LLM-extracted draft, pending user review/confirmation before create."""

    institution: str
    degree: str = ""
    field_of_study: str = ""
    start_date: date | None = None
    end_date: date | None = None
    description: str = ""


class ProfileExtractResponse(BaseModel):
    """Response for a CV/resume upload: drafts only, nothing written yet."""

    employment: List[EmploymentDraft] = Field(default_factory=list)
    education: List[EducationDraft] = Field(default_factory=list)


class TargetRoleCreate(BaseModel):
    """Role title + location to sample real postings for - not a hand-typed
    skill list. See ``TargetRoleRead.required_skills``."""

    title: str
    location: str = ""
    country: str = ""


class TargetRoleRead(BaseModel):
    id: str
    title: str
    location: str = ""
    country: str = ""
    # Derived from the market sample (see backend/app/tasks/role_tasks.py);
    # never set directly by the client.
    required_skills: List[str] = Field(default_factory=list)
    sample_status: str = "idle"
    sample_job_count: int = 0
    last_sampled_at: str | None = None


class TargetRoleUpdate(BaseModel):
    title: str | None = None
    location: str | None = None
    country: str | None = None


class TargetRoleRefreshResponse(BaseModel):
    id: str
    sample_status: str
    task_id: str | None = None


class PersonProfileRead(BaseModel):
    """Full contact/header profile, as rendered on the generated CV."""

    name: str = ""
    email: str = ""
    bio: str = ""
    phone: str = ""
    location: str = ""
    linkedin_url: str = ""
    github_url: str = ""
    website_url: str = ""
    languages_spoken: str = ""
    interests: str = ""
    awards: List[str] = Field(default_factory=list)


class PersonProfileUpdate(BaseModel):
    """Partial update for the contact/header profile. Unset fields are left
    untouched (as opposed to being cleared to their default)."""

    bio: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    website_url: str | None = None
    languages_spoken: str | None = None
    interests: str | None = None
    awards: List[str] | None = None


class ProfileSummary(BaseModel):
    """Aggregate career stats for the Career Experience tab header."""

    total_years_experience: float = 0.0
    employment_count: int = 0
    education_count: int = 0
    target_role_count: int = 0
    current_title: str | None = None
    current_company: str | None = None
