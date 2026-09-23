from __future__ import annotations

from pydantic import BaseModel


class SkillCreate(BaseModel):
    name: str
    category: str
    level: str


class SkillRead(SkillCreate):
    id: str


class SkillDemand(BaseModel):
    name: str
    demand: int
    # True when the skill is already in the requesting person's own skill
    # set - lets the Market Demand panel mark it "owned" instead of
    # treating every listed skill as something to learn.
    is_owned: bool = False


class SkillGap(BaseModel):
    skill: str
    gap_reason: str
    priority: str
    kind: str = "missing"  # "missing" | "underleveled"
    current_level: str | None = None
    expected_level: str | None = None
    demand: int = 0


class LearningPhase(BaseModel):
    """One ordered step of a :class:`LearningRoadmap`."""

    title: str
    duration: str = ""
    goal: str = ""
    # Atomic study topics (e.g. "chunking strategies"), never vague
    # "read about X" filler - see LEARNING_ROADMAP_PROMPT.
    concepts: list[str] = []
    steps: list[str] = []
    # Title of a SuggestedProject the candidate chose to include, scheduled
    # onto this phase - None when no included project fits.
    project_title: str | None = None


class LearningRoadmap(BaseModel):
    overview: str = ""
    overall_duration: str = ""
    phases: list[LearningPhase] = []


class SuggestedProject(BaseModel):
    """A comprehensive multi-skill project idea from skill-gap analysis."""

    title: str
    description: str = ""
    tech_stack: list[str] = []
    skills_covered: list[str] = []
    key_steps: list[str] = []
    deliverables: list[str] = []


class LearningRoadmapRequest(BaseModel):
    """Generate a roadmap from the unified "skills to learn" chip set,
    optionally scheduling projects the candidate already chose to build."""

    skills: list[str]
    target_role_id: str | None = None
    included_projects: list[SuggestedProject] = []


class LearningRoadmapCache(BaseModel):
    """Persisted roadmap (survives container restarts) - mirrors
    :class:`SuggestedProjectsCache`."""

    roadmap: LearningRoadmap | None = None
    cached: bool = False


class SuggestedProjectsRequest(BaseModel):
    """Regenerate portfolio projects from an explicit skill set."""

    skills: list[str]


class SuggestedProjectsCache(BaseModel):
    """Persisted project suggestions (survives container restarts)."""

    suggested_projects: list[SuggestedProject] = []
    skills: list[str] = []
    cached: bool = False


class SkillAnalysisResponse(BaseModel):
    """Fast, deterministic skill-gap result - see
    :class:`app.pipelines.skill_analysis_pipeline.SkillAnalysisPipeline`.
    Suggested projects and the learning roadmap are separate, explicit
    generations (see ``/suggested-projects`` and ``/learning-roadmap``),
    not part of this response.
    """

    core_strengths: list[str] = []
    skill_gaps: list[SkillGap] = []
    target_role_ready: bool = True
    target_role_title: str | None = None
    sample_status: str | None = None
    sample_job_count: int = 0
    error: str | None = None
