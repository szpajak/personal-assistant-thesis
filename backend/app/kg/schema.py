from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List


@dataclass
class Person:
    id: str
    name: str
    email: str
    # Optional short bio shown on the generated public portfolio site
    # (backend/scripts/generate_portfolio_site.py). Empty by default; set via
    # PATCH /api/v1/profile/me or directly in the KG.
    bio: str = ""
    # Contact/header details rendered on the generated CV (see
    # CVService.format_cv_markdown). All optional, set via PATCH
    # /api/v1/profile/me; omitted from the CV when blank.
    phone: str = ""
    location: str = ""
    linkedin_url: str = ""
    github_url: str = ""
    website_url: str = ""
    # Free-text "Additional Information" section on the CV.
    languages_spoken: str = ""
    interests: str = ""
    # Free-text bullets merged with real Certificate nodes into the CV's
    # "Certifications & Awards" section (e.g. "Employee of the Quarter (2022)").
    awards: List[str] = field(default_factory=list)


@dataclass
class Project:
    id: str
    title: str
    description: str
    tech_stack: List[str]
    start_date: date
    end_date: date | None
    media_urls: List[str]
    seniority: str | None = None
    achievements: List[str] = field(default_factory=list)
    # planned / in_progress: USES only. finished: also grants HAS_SKILL
    # (acquired skill). See KGIngestion.ingest_project / PortfolioService.
    status: str = "in_progress"


@dataclass
class Skill:
    id: str
    name: str
    category: str
    level: str


@dataclass
class JobOffer:
    """Promoted career-graph offer — embeddings, REQUIRES edges, applications/CV.

    Scraped-but-not-promoted listings are NOT modeled here anymore - they
    live in Postgres (``app/models/job_listing.py::ScrapedJobListing``) so the
    graph only ever holds jobs the user deliberately saved.
    """

    id: str
    title: str
    company: str
    url: str
    description: str
    required_skills: List[str]
    scraped_at: datetime
    status: str = "active"
    # Filled by KGIngestion.promote_job: one structured LLM analysis call
    # (JOB_ANALYSIS_PROMPT), seeded/falling back to the same regex heuristics
    # used at scrape time (app/utils/job_level.py) when the LLM call fails.
    seniority: str | None = None
    min_experience_years: int | None = None
    max_experience_years: int | None = None
    # "career" (default/missing, promoted by the user) or "market_sample"
    # (auto-scraped market context for a TargetRole's skill-gap analysis -
    # see KGIngestion.ingest_market_sample_job). Every query that means
    # "the user's own jobs" (career listing, global market demand, active
    # job ids for matching) must exclude market_sample offers.
    purpose: str = "career"


@dataclass
class Company:
    id: str
    name: str
    industry: str
    website: str


@dataclass
class Application:
    id: str
    status: str
    applied_at: datetime
    notes: str | None


@dataclass
class Email:
    id: str
    subject: str
    sender: str
    received_at: datetime
    summary: str
    classification: str


@dataclass
class LearningResource:
    id: str
    title: str
    url: str
    type: str
    skill_id: str


@dataclass
class Certificate:
    id: str
    title: str
    issuer: str
    issued_at: datetime
    document_url: str


@dataclass
class Document:
    """Arbitrary uploaded/parsed document (CV, cover letter, cert scan, ...).

    Written by ``KGIngestion.ingest_document``. Distinct from the typed
    ``Certificate``/``Project`` extraction flows, which parse a document and
    then discard it once structured entities are written.
    """

    id: str
    type: str
    title: str
    source: str
    content: str


@dataclass
class Employment:
    """A single job/role held by the person (career chronology)."""

    id: str
    title: str
    company: str
    start_date: date
    end_date: date | None
    description: str
    achievements: List[str] = field(default_factory=list)


@dataclass
class Education:
    """A single degree/program studied by the person (career chronology)."""

    id: str
    institution: str
    degree: str
    field_of_study: str
    start_date: date
    end_date: date | None
    description: str = ""


@dataclass
class SkillDemandSnapshot:
    """A dated market-demand reading for one skill (count of career JobOffers
    requiring it at the time of the snapshot).

    Written nightly by ``tasks.kg_tasks.record_skill_demand_snapshot``,
    building a time series that ``JobOffer.REQUIRES`` counts alone (a single
    live aggregate) cannot provide - trend direction, not just current level.
    """

    id: str
    skill_id: str
    demand_count: int
    snapshot_date: date


@dataclass
class TargetRole:
    """A role/title the person is aiming for, benchmarked against a real
    sample of scraped job postings for that title/location rather than a
    hand-typed skill list.

    ``required_skills`` is *derived* - written by the sampling task
    (``app.tasks.role_tasks.refresh_target_role_sample``) from the REQUIRES
    demand aggregate over this role's sampled ``JobOffer``s - so skill-gap
    analysis reflects real market data instead of a best-effort GraphRAG
    match against an arbitrary title.
    """

    id: str
    title: str
    location: str = ""
    country: str = ""
    required_skills: List[str] = field(default_factory=list)
    # idle (never sampled) | scraping | ingesting | ready | error
    sample_status: str = "idle"
    sample_job_count: int = 0
    last_sampled_at: str | None = None
