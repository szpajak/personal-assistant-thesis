from __future__ import annotations

from datetime import date
from typing import Any, List, Literal

from pydantic import BaseModel, Field, field_validator

SkillCategory = Literal["technical", "soft", "language", "tool", "framework"]
SkillLevel = Literal["beginner", "intermediate", "advanced", "expert"]
ProjectSeniority = Literal["junior", "mid", "senior", "lead"]
ProjectStatus = Literal["planned", "in_progress", "finished"]

# LLMs frequently return category/seniority/level labels that are close to,
# but not exactly in, our controlled vocabulary (e.g. "library" instead of
# "framework"). Coerce common synonyms instead of raising a validation error
# and dropping the whole extraction/enrichment result.
_CATEGORY_SYNONYMS = {
    "library": "framework",
    "libraries": "framework",
    "platform": "tool",
    "database": "tool",
    "db": "tool",
    "cloud": "tool",
    "programming_language": "language",
    "programming language": "language",
    "spoken_language": "language",
    "spoken language": "language",
    "methodology": "soft",
    "soft_skill": "soft",
    "soft skill": "soft",
    "interpersonal": "soft",
}
_LEVEL_SYNONYMS = {
    "novice": "beginner",
    "basic": "beginner",
    "junior": "beginner",
    "familiar": "beginner",
    "proficient": "intermediate",
    "competent": "intermediate",
    "mid": "intermediate",
    "skilled": "advanced",
    "senior": "advanced",
    "master": "expert",
    "specialist": "expert",
    "guru": "expert",
}
_VALID_CATEGORIES = {"technical", "soft", "language", "tool", "framework"}
_VALID_LEVELS = {"beginner", "intermediate", "advanced", "expert"}
_VALID_SENIORITY = {"junior", "mid", "senior", "lead"}


def _coerce_category(value: Any) -> str:
    """Map a raw LLM-provided category string onto our controlled vocabulary."""
    if not isinstance(value, str):
        return "technical"
    normalized = value.strip().lower()
    if normalized in _VALID_CATEGORIES:
        return normalized
    return _CATEGORY_SYNONYMS.get(normalized, "technical")


def coerce_skill_level(value: Any) -> str:
    """Map a raw LLM/user-provided level string onto our controlled vocabulary.

    Defaults to "intermediate" only when the value is missing/unrecognized -
    callers that need to distinguish "not assessed" from "intermediate" should
    check for None/empty input themselves before calling this.
    """
    if not isinstance(value, str):
        return "intermediate"
    normalized = value.strip().lower()
    if normalized in _VALID_LEVELS:
        return normalized
    return _LEVEL_SYNONYMS.get(normalized, "intermediate")


def coerce_seniority(value: Any) -> str | None:
    """Map a raw LLM-provided seniority string onto our controlled vocabulary."""
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized if normalized in _VALID_SENIORITY else None


class SkillDraft(BaseModel):
    """A single skill as proposed by the user (form) or the LLM (enrichment
    suggestions / document extraction).
    """

    name: str
    canonical_name: str | None = None
    category: SkillCategory = "technical"
    level: SkillLevel = "intermediate"
    confidence: float = 1.0

    @field_validator("category", mode="before")
    @classmethod
    def _validate_category(cls, value: Any) -> str:
        return _coerce_category(value)

    @field_validator("level", mode="before")
    @classmethod
    def _validate_level(cls, value: Any) -> str:
        return coerce_skill_level(value)


class ProjectDraft(BaseModel):
    """LLM-produced draft for a project, pending user review/confirmation.

    Never written to the graph directly - the frontend shows this for
    edit/confirm, then submits it (or an edited version of it) as a
    ``ProjectCreate`` with ``skip_enrichment=True``.
    """

    title: str
    description: str
    skills: List[SkillDraft] = Field(default_factory=list)
    tech_stack: List[str] = Field(default_factory=list)
    start_date: date | None = None
    end_date: date | None = None
    media_urls: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)
    seniority: ProjectSeniority | None = None
    source: Literal["form", "upload"] = "form"

    @field_validator("seniority", mode="before")
    @classmethod
    def _validate_seniority(cls, value: Any) -> str | None:
        return coerce_seniority(value)


class ProjectCreate(BaseModel):
    title: str
    description: str
    tech_stack: List[str] = Field(default_factory=list)
    start_date: date
    end_date: date | None = None
    media_urls: List[str] = Field(default_factory=list)
    seniority: ProjectSeniority | None = None
    achievements: List[str] = Field(default_factory=list)
    skills: List[SkillDraft] = Field(default_factory=list)
    skip_enrichment: bool = False
    status: ProjectStatus = "in_progress"

    @field_validator("seniority", mode="before")
    @classmethod
    def _validate_seniority(cls, value: Any) -> str | None:
        return coerce_seniority(value)


class ProjectUpdate(BaseModel):
    """Partial update for an existing portfolio project."""

    title: str | None = None
    description: str | None = None
    tech_stack: List[str] | None = None
    start_date: date | None = None
    end_date: date | None = None
    media_urls: List[str] | None = None
    seniority: ProjectSeniority | None = None
    achievements: List[str] | None = None
    skills: List[SkillDraft] | None = None
    status: ProjectStatus | None = None

    @field_validator("seniority", mode="before")
    @classmethod
    def _validate_seniority(cls, value: Any) -> str | None:
        return coerce_seniority(value)


class ProjectRead(ProjectCreate):
    id: str


class PublicSkill(BaseModel):
    name: str
    category: str
    level: str


class PublicCertificate(BaseModel):
    title: str
    issuer: str
    issued_at: str | None = None


class PublicEmployment(BaseModel):
    title: str
    company: str
    start_date: date | None = None
    end_date: date | None = None
    description: str = ""
    achievements: List[str] = Field(default_factory=list)


class PublicEducation(BaseModel):
    institution: str
    degree: str
    field_of_study: str = ""
    start_date: date | None = None
    end_date: date | None = None
    description: str = ""


class PublicPortfolioExport(BaseModel):
    """Read-only, public subset of a Person's KG used to render the static
    portfolio site (backend/scripts/generate_portfolio_site.py) and served
    directly for any other public consumer (e.g. a future JS widget).

    Deliberately excludes anything not meant to be public: Application,
    Email, JobOffer, LearningResource, raw embeddings, target roles. Only
    non-``planned`` projects are included - a planned project is a to-do
    item, not evidence of finished/ongoing work.
    """

    name: str
    bio: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin_url: str = ""
    github_url: str = ""
    website_url: str = ""
    awards: List[str] = Field(default_factory=list)
    projects: List[ProjectRead] = Field(default_factory=list)
    skills: List[PublicSkill] = Field(default_factory=list)
    certificates: List[PublicCertificate] = Field(default_factory=list)
    employment: List[PublicEmployment] = Field(default_factory=list)
    education: List[PublicEducation] = Field(default_factory=list)


class ProjectExtractResponse(BaseModel):
    """Response for document upload: drafts only, nothing written to the KG yet."""

    drafts: List[ProjectDraft] = Field(default_factory=list)
