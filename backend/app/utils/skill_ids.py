"""Canonical skill ID helpers shared across ingestion and user skills."""

from __future__ import annotations

import hashlib
import re

# Common synonyms / abbreviations that would otherwise slugify into distinct
# Skill nodes for the same real-world skill (e.g. "React.js" -> "react_js" vs
# "React" -> "react"). Keys are lowercased + whitespace-collapsed before
# lookup; values are the canonical *display* name written to Skill.name.
# This is a lightweight, static entity-resolution layer - see
# ``resolve_canonical_skill_name``. Periodic embedding-based near-duplicate
# detection for names not covered here lives in ``tasks/kg_tasks.py``
# (``merge_duplicate_skills``).
SKILL_ALIASES: dict[str, str] = {
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ecmascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "py": "Python",
    "python": "Python",
    "python3": "Python",
    "reactjs": "React",
    "react.js": "React",
    "react js": "React",
    "vuejs": "Vue",
    "vue.js": "Vue",
    "vue js": "Vue",
    "angularjs": "Angular",
    "angular.js": "Angular",
    "nextjs": "Next.js",
    "next js": "Next.js",
    "nodejs": "Node.js",
    "node js": "Node.js",
    "node": "Node.js",
    "expressjs": "Express",
    "express.js": "Express",
    "nestjs": "NestJS",
    "nest.js": "NestJS",
    "golang": "Go",
    "c sharp": "C#",
    "csharp": "C#",
    "c plus plus": "C++",
    "cpp": "C++",
    "dotnet": ".NET",
    ".net core": ".NET",
    "asp.net": ".NET",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "psql": "PostgreSQL",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "Google Cloud Platform",
    "google cloud": "Google Cloud Platform",
    "azure": "Microsoft Azure",
    "html5": "HTML",
    "html": "HTML",
    "css3": "CSS",
    "css": "CSS",
    "scss": "Sass",
    "sass": "Sass",
    "tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "deep learning": "Deep Learning",
    "dl": "Deep Learning",
    "ai": "Artificial Intelligence",
    "artificial intelligence": "Artificial Intelligence",
    "nlp": "Natural Language Processing",
    "natural language processing": "Natural Language Processing",
    "nlu": "Natural Language Understanding",
    "natural language understanding": "Natural Language Understanding",
    "llm": "Large Language Models",
    "large language models": "Large Language Models",
    "llms": "Large Language Models",
    "langchain": "LangChain",
    "langgraph": "LangGraph",
    "rag": "RAG",
    "retrieval augmented generation": "RAG",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "sklearn": "scikit-learn",
    "scikit-learn": "scikit-learn",
    "scikit learn": "scikit-learn",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "spring boot": "Spring Boot",
    "springboot": "Spring Boot",
    "kafka": "Kafka",
    "apache kafka": "Kafka",
    "spark": "Apache Spark",
    "apache spark": "Apache Spark",
    "redis": "Redis",
    "neo4j": "Neo4j",
    "terraform": "Terraform",
    "ansible": "Ansible",
    "cicd": "CI/CD",
    "ci/cd": "CI/CD",
    "ci cd": "CI/CD",
    "rest": "REST API",
    "restful": "REST API",
    "rest api": "REST API",
    "graphql": "GraphQL",
    "docker": "Docker",
    "git": "Git",
    "github": "Git",
    "gitlab": "GitLab",
    "jira": "Jira",
    "aws certified": "AWS Certification",
    "cka": "CKA",
    "ckad": "CKAD",
}


# Categories kept when LLM extraction returns structured skill objects.
TECH_SKILL_CATEGORIES: frozenset[str] = frozenset(
    {
        "technical",
        "tool",
        "framework",
        "language",
        "certificate",
        "certification",
        "library",
        "platform",
        "database",
    }
)

# Soft / process jargon to drop even if the model mis-labels the category.
SOFT_SKILL_BLOCKLIST: frozenset[str] = frozenset(
    {
        "collaboration",
        "communication",
        "teamwork",
        "leadership",
        "problem solving",
        "problem-solving",
        "critical thinking",
        "time management",
        "adaptability",
        "creativity",
        "plan-and-solve",
        "plan and solve",
        "agile mindset",
        "self-motivated",
        "self motivated",
        "attention to detail",
        "ownership",
        "mentoring",
        "stakeholder management",
    }
)


# Shared proficiency ordering: used both when merging a person's own Skill
# level across projects (ingestion.py's ``_higher_skill_level``) and when
# comparing a candidate's level against a job's typical ``REQUIRES.level``
# for gap analysis (skill_analysis_pipeline.py). Unrecognized/missing values
# rank 0 (lowest).
SKILL_LEVEL_RANK: dict[str, int] = {
    "beginner": 1,
    "intermediate": 2,
    "advanced": 3,
    "expert": 4,
}


def skill_level_rank(level: str | None) -> int:
    """Numeric proficiency rank for a skill level string (0 = unknown)."""
    return SKILL_LEVEL_RANK.get(str(level or "").strip().lower(), 0)


def _normalize(name: str) -> str:
    """Lowercase + collapse whitespace/punctuation for alias/id lookups."""
    return re.sub(r"\s+", " ", name.strip().lower())


def resolve_canonical_skill_name(name: str) -> str:
    """Resolve a raw, possibly-abbreviated skill name to its canonical display form.

    Looks the normalized name up in :data:`SKILL_ALIASES`; falls back to the
    original (trimmed) name when there is no known alias, so unseen skills
    are never dropped - only known synonyms are merged.
    """
    normalized = _normalize(name)
    return SKILL_ALIASES.get(normalized, name.strip())


def is_soft_or_irrelevant_skill(name: str) -> bool:
    """Return True for soft/process skills that should not appear on job tech stacks."""
    return _normalize(name) in SOFT_SKILL_BLOCKLIST


def canonicalize_skill_list(skills: list[str] | None) -> list[str]:
    """Canonicalize + case-insensitive dedupe a skill name list (order preserved)."""
    result: list[str] = []
    seen: set[str] = set()
    for raw in skills or []:
        if not isinstance(raw, str):
            continue
        name = resolve_canonical_skill_name(raw)
        if not name or is_soft_or_irrelevant_skill(name):
            continue
        key = _normalize(name)
        if key in seen:
            continue
        seen.add(key)
        result.append(name)
    return result


def filter_extracted_skill_objects(skills_data: list) -> list[str]:
    """Keep tech-relevant names from LLM skill objects; drop soft/professional noise."""
    names: list[str] = []
    for skill in skills_data:
        if not isinstance(skill, dict):
            continue
        raw_name = skill.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            continue
        category = str(skill.get("category") or "").strip().lower()
        if category and category not in TECH_SKILL_CATEGORIES:
            continue
        if is_soft_or_irrelevant_skill(raw_name):
            continue
        names.append(raw_name)
    return canonicalize_skill_list(names)


def canonical_skill_id(name: str) -> str:
    """Build a stable skill node ID from a display name.

    Resolves known aliases first so e.g. "React.js" and "React" collapse to
    the same node instead of creating duplicates.
    """
    canonical_name = resolve_canonical_skill_name(name)
    normalized = re.sub(r"[^a-z0-9]+", "_", canonical_name.lower()).strip("_")
    return f"skill_{normalized}" if normalized else "skill_unknown"


def company_id(name: str) -> str:
    """Build a stable company node ID from a display name."""
    normalized = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"company_{normalized}" if normalized else "company_unknown"


def learning_resource_id(skill_id: str, title: str) -> str:
    """Deterministic ID for a LearningResource so re-running skill analysis
    updates the same node instead of spawning duplicates on every run.
    """
    digest = hashlib.sha1(f"{skill_id}:{_normalize(title)}".encode()).hexdigest()[:16]
    return f"learning_{digest}"


def employment_id(company: str, title: str, start_date: str) -> str:
    """Deterministic ID for an Employment record (idempotent re-ingestion)."""
    digest = hashlib.sha1(
        f"{_normalize(company)}:{_normalize(title)}:{start_date}".encode()
    ).hexdigest()[:16]
    return f"employment_{digest}"


def education_id(institution: str, degree: str, start_date: str) -> str:
    """Deterministic ID for an Education record (idempotent re-ingestion)."""
    digest = hashlib.sha1(
        f"{_normalize(institution)}:{_normalize(degree)}:{start_date}".encode()
    ).hexdigest()[:16]
    return f"education_{digest}"


def target_role_id(title: str) -> str:
    """Deterministic ID for a TargetRole node."""
    normalized = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return f"target_role_{normalized}" if normalized else "target_role_unknown"
