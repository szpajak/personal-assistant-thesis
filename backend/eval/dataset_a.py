"""Dataset A: labelled career PKG plus qrels and task gold.

The person is a mid-level Python/backend engineer with GraphRAG experience and
a little Kubernetes. Job postings mix synthetic fixtures with **real** offers
copied from the author's Neo4j (titles/companies/descriptions; skill lists
curated for stable gap gold). See ``docs/evaluation/JOB_GRADES.md``.
"""

from __future__ import annotations

from typing import Any, TypedDict


PERSON_A = "eval_person_a"
PERSON_B = "eval_person_b"

REQUIRED_LABELS = {
    "Person",
    "Project",
    "Skill",
    "JobOffer",
    "Company",
    "Application",
    "Email",
    "Certificate",
    "Employment",
    "Education",
    "TargetRole",
}

REQUIRED_RELS = {
    "HAS_SKILL",
    "PRODUCED",
    "USES",
    "REQUIRES",
    "POSTED_BY",
    "APPLIED_TO",
    "FOR_OFFER",
    "HAS_CERTIFICATE",
    "VALIDATES",
    "WORKED_AT",
    "STUDIED_AT",
    "RECEIVED",
    "HAS_EMAIL",
    "FROM_COMPANY",
    "SAVED",
    "AIMS_FOR",
    "SAMPLED",
}


class SkillDraft(TypedDict):
    name: str
    canonical_name: str
    category: str
    level: str
    confidence: float


def _skill(name: str, canonical: str, level: str, category: str = "technical") -> SkillDraft:
    return {
        "name": name,
        "canonical_name": canonical,
        "category": category,
        "level": level,
        "confidence": 1.0,
    }


PERSON_A_PROFILE: dict[str, Any] = {
    "id": PERSON_A,
    "name": "Alex Nowak",
    "email": "alex.nowak.eval@example.com",
    "bio": "Backend engineer building graph-grounded career tools.",
    "phone": "+48 600 000 000",
    "location": "Warsaw",
    "linkedin_url": "https://linkedin.com/in/alex-nowak-eval",
    "github_url": "https://github.com/alex-nowak-eval",
}

EDUCATION = {
    "institution": "Warsaw University of Technology",
    "degree": "MSc",
    "field_of_study": "Computer Science",
    "start_date": "2019-10-01",
    "end_date": "2021-06-30",
    "description": "Thesis on information retrieval.",
}

EMPLOYMENT = {
    "title": "Backend Engineer",
    "company": "FinTechCo",
    "start_date": "2022-03-01",
    "end_date": None,
    "description": "APIs and data pipelines in Python and FastAPI.",
    "skills": ["Python", "FastAPI", "PostgreSQL"],
}

# Keys are stable handles used by qrels / scenarios. Ingestion assigns UUIDs.
PROJECTS: dict[str, dict[str, Any]] = {
    "graphrag": {
        "title": "Personal GraphRAG Career Assistant",
        "description": (
            "Task-oriented assistant over a Neo4j personal knowledge graph. "
            "Hybrid vector and full-text retrieval with one-hop expansion "
            "grounds CV generation and job matching."
        ),
        "tech_stack": ["Python", "FastAPI", "Neo4j", "LangChain"],
        "status": "finished",
        "seniority": "mid",
        "start_date": "2025-01-10",
        "end_date": "2025-08-01",
        "achievements": ["Hybrid GraphRAG retriever", "LangGraph pipelines"],
        "skills": [
            _skill("Python", "Python", "expert"),
            _skill("FastAPI", "FastAPI", "advanced"),
            _skill("Neo4j", "Neo4j", "advanced"),
            _skill("LangChain", "LangChain", "advanced"),
        ],
    },
    "scraper": {
        "title": "Job Board Scraper",
        "description": "Scrapes LinkedIn and Indeed listings into a staging store.",
        "tech_stack": ["Python", "BeautifulSoup"],
        "status": "finished",
        "seniority": "junior",
        "start_date": "2024-02-01",
        "end_date": "2024-05-01",
        "achievements": ["Deduplicated listings by URL"],
        "skills": [
            _skill("Python", "Python", "advanced"),
            _skill("BeautifulSoup", "BeautifulSoup", "intermediate"),
        ],
    },
    "dashboard": {
        "title": "Hiring Dashboard",
        "description": "React.js dashboard for application Kanban and skill charts.",
        "tech_stack": ["React.js", "TypeScript", "Tailwind"],
        "status": "finished",
        "seniority": "mid",
        "start_date": "2024-06-01",
        "end_date": "2024-11-01",
        "achievements": ["Kanban board", "Chart views"],
        "skills": [
            _skill("React.js", "React", "intermediate"),
            _skill("TypeScript", "TypeScript", "advanced"),
            _skill("Tailwind", "Tailwind CSS", "intermediate"),
        ],
    },
    "k8s": {
        "title": "Kubernetes Toy Deploy",
        "description": "First k8s deployment of a hello-world API; beginner exercise.",
        "tech_stack": ["k8s", "Docker"],
        "status": "finished",
        "seniority": "junior",
        "start_date": "2023-09-01",
        "end_date": "2023-10-01",
        "achievements": ["Single-node cluster"],
        "skills": [
            _skill("k8s", "Kubernetes", "beginner"),
            _skill("Docker", "Docker", "intermediate"),
        ],
    },
    "spark": {
        "title": "Spark ETL Warehouse",
        "description": "Apache Spark jobs loading events into postgres analytics tables.",
        "tech_stack": ["Apache Spark", "postgres", "Python"],
        "status": "finished",
        "seniority": "mid",
        "start_date": "2023-01-01",
        "end_date": "2023-08-01",
        "achievements": ["Daily batch pipeline"],
        "skills": [
            _skill("Apache Spark", "Apache Spark", "advanced"),
            _skill("postgres", "PostgreSQL", "advanced"),
            _skill("Python", "Python", "advanced"),
        ],
    },
    "rag_bot": {
        "title": "LangChain RAG Chatbot",
        "description": "Document QA chatbot using LangChain retrievers over PDFs.",
        "tech_stack": ["LangChain", "Python"],
        "status": "finished",
        "seniority": "mid",
        "start_date": "2024-09-01",
        "end_date": "2024-12-01",
        "achievements": ["Cited answers"],
        "skills": [
            _skill("LangChain", "LangChain", "advanced"),
            _skill("Python", "Python", "advanced"),
        ],
    },
    "rest_api": {
        "title": "Payments REST API",
        "description": "FastAPI service with PostgreSQL persistence for payments.",
        "tech_stack": ["FastAPI", "PostgreSQL"],
        "status": "finished",
        "seniority": "mid",
        "start_date": "2022-06-01",
        "end_date": "2023-01-01",
        "achievements": ["Idempotent payments"],
        "skills": [
            _skill("FastAPI", "FastAPI", "advanced"),
            _skill("PostgreSQL", "PostgreSQL", "advanced"),
        ],
    },
    "tutorial": {
        "title": "Beginner Python Course Site",
        "description": "Static tutorial site teaching Python basics to novices.",
        "tech_stack": ["Python", "HTML"],
        "status": "finished",
        "seniority": "junior",
        "start_date": "2021-03-01",
        "end_date": "2021-06-01",
        "achievements": ["12 lessons"],
        "skills": [
            _skill("Python", "Python", "beginner"),
            _skill("HTML", "HTML", "intermediate"),
        ],
    },
    "flutter": {
        "title": "Flutter Habit Tracker",
        "description": "In-progress mobile app; skills not yet acquired.",
        "tech_stack": ["Flutter", "Dart"],
        "status": "in_progress",
        "seniority": "junior",
        "start_date": "2026-01-15",
        "end_date": None,
        "achievements": [],
        "skills": [
            _skill("Flutter", "Flutter", "beginner"),
            _skill("Dart", "Dart", "beginner"),
        ],
    },
    "rust_plan": {
        "title": "Rust Rewrite Spike",
        "description": "Planned rewrite of a CLI in Rust.",
        "tech_stack": ["Rust"],
        "status": "planned",
        "seniority": "junior",
        "start_date": "2026-09-01",
        "end_date": None,
        "achievements": [],
        "skills": [_skill("Rust", "Rust", "beginner")],
    },
}

PERSON_B_PROJECT = {
    "title": "Secret Quantum Compiler",
    "description": "Proprietary quantum IR compiler; must never leak to person A retrieval.",
    "tech_stack": ["Qiskit", "Python"],
    "status": "finished",
    "seniority": "senior",
    "start_date": "2024-01-01",
    "end_date": "2024-12-01",
    "achievements": ["Internal only"],
    "skills": [_skill("Qiskit", "Qiskit", "expert")],
}

CERTIFICATE = {
    "title": "AWS Certified Cloud Practitioner",
    "issuer": "Amazon",
    "issued_at": "2024-04-01",
    "document_url": "https://example.com/certs/aws-ccp.pdf",
    "validated_skills": ["AWS"],
}

# Job keys, graded relevance 0/1/2 for PERSON_A, plus REQUIRES levels.
# Keys prefixed ``real_`` are adapted from the author's live Neo4j snapshot
# (docs/evaluation/real_jobs_snapshot.json). Skill lists are curated (core
# stack only) so TargetRole gap gold stays exhaustive and stable.
JOBS: dict[str, dict[str, Any]] = {
    "graphrag_role": {
        "title": "GraphRAG Python Engineer",
        "company": "Acme AI",
        "url": "https://jobs.eval.example/acme-graphrag",
        "description": (
            "Build graph-augmented retrieval over Neo4j. Python, FastAPI, "
            "LangChain. Mid/senior backend with knowledge graphs."
        ),
        "skills": [
            {"name": "Python", "level": "advanced", "importance": "required"},
            {"name": "Neo4j", "level": "advanced", "importance": "required"},
            {"name": "FastAPI", "level": "intermediate", "importance": "required"},
            {"name": "LangChain", "level": "intermediate", "importance": "preferred"},
        ],
        "relevance": 2,
        "apply": True,
        "source": "synthetic",
    },
    "fastapi_backend": {
        "title": "Mid Backend Engineer FastAPI",
        "company": "Beta Labs",
        "url": "https://jobs.eval.example/beta-fastapi",
        "description": "Python services with FastAPI and PostgreSQL.",
        "skills": [
            {"name": "Python", "level": "advanced", "importance": "required"},
            {"name": "FastAPI", "level": "advanced", "importance": "required"},
            {"name": "PostgreSQL", "level": "intermediate", "importance": "required"},
        ],
        "relevance": 2,
        "apply": True,
        "source": "synthetic",
    },
    "k8s_platform": {
        "title": "Platform Engineer Kubernetes",
        "company": "CloudCo",
        "url": "https://jobs.eval.example/cloudco-k8s",
        "description": "Production Kubernetes and Docker. Some Python glue.",
        "skills": [
            {"name": "Kubernetes", "level": "advanced", "importance": "required"},
            {"name": "Docker", "level": "intermediate", "importance": "required"},
            {"name": "Python", "level": "intermediate", "importance": "preferred"},
        ],
        "relevance": 1,
        "apply": False,
        "source": "synthetic",
    },
    "data_eng": {
        "title": "Data Engineer Spark",
        "company": "DataCorp",
        "url": "https://jobs.eval.example/datacorp-spark",
        "description": "Spark ETL and warehouse modelling in Python.",
        "skills": [
            {"name": "Apache Spark", "level": "advanced", "importance": "required"},
            {"name": "Python", "level": "advanced", "importance": "required"},
            {"name": "PostgreSQL", "level": "advanced", "importance": "required"},
        ],
        "relevance": 1,
        "apply": False,
        "source": "synthetic",
    },
    "frontend": {
        "title": "Frontend Engineer React",
        "company": "Webify",
        "url": "https://jobs.eval.example/webify-react",
        "description": "React and TypeScript product UI. Not a backend role.",
        "skills": [
            {"name": "React", "level": "advanced", "importance": "required"},
            {"name": "TypeScript", "level": "advanced", "importance": "required"},
            {"name": "CSS", "level": "intermediate", "importance": "preferred"},
        ],
        "relevance": 1,
        "apply": False,
        "source": "synthetic",
    },
    "java_bank": {
        "title": "Java Spring Backend",
        "company": "National Bank",
        "url": "https://jobs.eval.example/bank-java",
        "description": "Java and Spring Boot microservices with Kafka.",
        "skills": [
            {"name": "Java", "level": "advanced", "importance": "required"},
            {"name": "Spring Boot", "level": "advanced", "importance": "required"},
            {"name": "Kafka", "level": "intermediate", "importance": "required"},
        ],
        "relevance": 0,
        "apply": True,
        "source": "synthetic",
    },
    "php": {
        "title": "WordPress PHP Developer",
        "company": "Agency Nine",
        "url": "https://jobs.eval.example/agency-php",
        "description": "PHP WordPress sites for marketing clients.",
        "skills": [
            {"name": "PHP", "level": "advanced", "importance": "required"},
            {"name": "WordPress", "level": "advanced", "importance": "required"},
            {"name": "CSS", "level": "intermediate", "importance": "preferred"},
        ],
        "relevance": 0,
        "apply": False,
        "source": "synthetic",
    },
    "go_sre": {
        "title": "SRE Go and Kubernetes",
        "company": "Infra LLC",
        "url": "https://jobs.eval.example/infra-go",
        "description": "Go services, Kubernetes, Terraform. On-call SRE.",
        "skills": [
            {"name": "Go", "level": "advanced", "importance": "required"},
            {"name": "Kubernetes", "level": "advanced", "importance": "required"},
            {"name": "Terraform", "level": "intermediate", "importance": "required"},
        ],
        "relevance": 0,
        "apply": False,
        "source": "synthetic",
    },
    "nlp": {
        "title": "NLP Research Scientist",
        "company": "Lab AI",
        "url": "https://jobs.eval.example/lab-nlp",
        "description": "PyTorch NLP research. Publications expected.",
        "skills": [
            {"name": "Python", "level": "advanced", "importance": "required"},
            {"name": "PyTorch", "level": "advanced", "importance": "required"},
            {"name": "Natural Language Processing", "level": "advanced", "importance": "required"},
        ],
        "relevance": 1,
        "apply": False,
        "source": "synthetic",
    },
    "junior_py": {
        "title": "Junior Python Developer",
        "company": "Startup Hub",
        "url": "https://jobs.eval.example/hub-junior",
        "description": "Entry-level Python and FastAPI. Mentored role.",
        "skills": [
            {"name": "Python", "level": "beginner", "importance": "required"},
            {"name": "FastAPI", "level": "beginner", "importance": "preferred"},
        ],
        "relevance": 1,
        "apply": False,
        "source": "synthetic",
    },
    "real_python_ai_backend": {
        "title": "Backend Engineer - Python AI",
        "company": "RiVi Consulting Group L.L.C",
        "url": "https://jobs.eval.example/real/rivi-python-ai",
        "description": (
            "Scale backend infrastructure and agentic capabilities: memory "
            "layers, RAG pipelines, ontological structures. Production "
            "asynchronous Python (FastAPI/Pydantic), LangGraph/LangChain "
            "agent loops, knowledge graphs / long-term memory."
        ),
        "skills": [
            {"name": "Python", "level": "advanced", "importance": "required"},
            {"name": "FastAPI", "level": "advanced", "importance": "required"},
            {"name": "LangChain", "level": "intermediate", "importance": "required"},
            {"name": "LangGraph", "level": "intermediate", "importance": "required"},
            {"name": "RAG", "level": "intermediate", "importance": "required"},
        ],
        "relevance": 2,
        "apply": True,
        "source": "real_graph",
    },
    "real_senior_ai": {
        "title": "Senior AI Engineer",
        "company": "First Advantage",
        "url": "https://jobs.eval.example/real/first-advantage-ai",
        "description": (
            "Senior AI Engineer (Krakow / remote). Build production AI "
            "services with Python and FastAPI, RAG pipelines, Dockerised "
            "deployments; Terraform for infra-as-code."
        ),
        "skills": [
            {"name": "Python", "level": "advanced", "importance": "required"},
            {"name": "FastAPI", "level": "advanced", "importance": "required"},
            {"name": "RAG", "level": "intermediate", "importance": "required"},
            {"name": "Docker", "level": "intermediate", "importance": "required"},
            {"name": "Terraform", "level": "intermediate", "importance": "preferred"},
        ],
        "relevance": 2,
        "apply": False,
        "source": "real_graph",
    },
    "real_ey_aiml": {
        "title": "AI/ML Engineer",
        "company": "EY",
        "url": "https://jobs.eval.example/real/ey-aiml",
        "description": (
            "AI/ML engineer building LLM applications with Python, FastAPI, "
            "LangChain/LangGraph, containerised services and Kubernetes."
        ),
        "skills": [
            {"name": "Python", "level": "advanced", "importance": "required"},
            {"name": "FastAPI", "level": "intermediate", "importance": "required"},
            {"name": "LangChain", "level": "intermediate", "importance": "required"},
            {"name": "LangGraph", "level": "intermediate", "importance": "preferred"},
            {"name": "Docker", "level": "intermediate", "importance": "required"},
            {"name": "Kubernetes", "level": "advanced", "importance": "preferred"},
        ],
        "relevance": 2,
        "apply": False,
        "source": "real_graph",
    },
    "real_tidio_ml": {
        "title": "Senior Machine Learning Engineer (NLP/LLMs)",
        "company": "Tidio",
        "url": "https://jobs.eval.example/real/tidio-ml",
        "description": (
            "Senior ML engineer for NLP/LLMs: PyTorch models, RAG, FastAPI "
            "serving. Strong research/ML focus beyond product backend."
        ),
        "skills": [
            {"name": "Python", "level": "advanced", "importance": "required"},
            {"name": "FastAPI", "level": "intermediate", "importance": "required"},
            {"name": "PyTorch", "level": "advanced", "importance": "required"},
            {"name": "Natural Language Processing", "level": "advanced", "importance": "required"},
            {"name": "RAG", "level": "intermediate", "importance": "preferred"},
        ],
        "relevance": 1,
        "apply": False,
        "source": "real_graph",
    },
    "real_cognism_mlops": {
        "title": "MLOps Engineer",
        "company": "Cognism",
        "url": "https://jobs.eval.example/real/cognism-mlops",
        "description": (
            "MLOps: CI/CD for models, Docker/Kubernetes, Terraform, Python "
            "services with FastAPI. Platform/ops-heavy rather than product APIs."
        ),
        "skills": [
            {"name": "Python", "level": "advanced", "importance": "required"},
            {"name": "FastAPI", "level": "intermediate", "importance": "preferred"},
            {"name": "Kubernetes", "level": "advanced", "importance": "required"},
            {"name": "Docker", "level": "intermediate", "importance": "required"},
            {"name": "Terraform", "level": "intermediate", "importance": "required"},
        ],
        "relevance": 1,
        "apply": False,
        "source": "real_graph",
    },
    "real_accenture_intern": {
        "title": "AI/MLOps Internship Program",
        "company": "Accenture",
        "url": "https://jobs.eval.example/real/accenture-intern",
        "description": (
            "Internship: Python, FastAPI, LangChain, Docker, cloud basics. "
            "Junior bar; good stack overlap but internship seniority."
        ),
        "skills": [
            {"name": "Python", "level": "intermediate", "importance": "required"},
            {"name": "FastAPI", "level": "beginner", "importance": "preferred"},
            {"name": "LangChain", "level": "beginner", "importance": "preferred"},
            {"name": "Docker", "level": "beginner", "importance": "preferred"},
        ],
        "relevance": 1,
        "apply": False,
        "source": "real_graph",
    },
    "real_arche_ai_py": {
        "title": "Senior AI & Python Engineer",
        "company": "ARCHE consulting",
        "url": "https://jobs.eval.example/real/arche-ai-py",
        "description": (
            "Senior AI & Python engineer across cloud and LLM products. "
            "Python-strong but broader AI consulting than GraphRAG backend."
        ),
        "skills": [
            {"name": "Python", "level": "advanced", "importance": "required"},
            {"name": "AWS", "level": "intermediate", "importance": "required"},
            {"name": "Machine Learning", "level": "intermediate", "importance": "required"},
        ],
        "relevance": 1,
        "apply": False,
        "source": "real_graph",
    },
    "real_jc_agentic": {
        "title": "Senior Data Scientist (Agentic AI Platform)",
        "company": "Johnson Controls",
        "url": "https://jobs.eval.example/real/jc-agentic",
        "description": (
            "Agentic AI platform: Python, FastAPI, LangChain/LangGraph, "
            "Kubernetes. Data-science title with strong eng overlap."
        ),
        "skills": [
            {"name": "Python", "level": "advanced", "importance": "required"},
            {"name": "FastAPI", "level": "intermediate", "importance": "required"},
            {"name": "LangChain", "level": "intermediate", "importance": "required"},
            {"name": "Kubernetes", "level": "intermediate", "importance": "preferred"},
        ],
        "relevance": 1,
        "apply": False,
        "source": "real_graph",
    },
    "real_gitlab_ruby": {
        "title": "Senior Backend Engineer (Ruby)",
        "company": "GitLab Inc",
        "url": "https://jobs.eval.example/real/gitlab-ruby",
        "description": (
            "Senior backend on Ruby on Rails / GraphQL. Some Python and SQL; "
            "primary stack is Ruby — poor fit for a Python GraphRAG engineer."
        ),
        "skills": [
            {"name": "Ruby on Rails", "level": "advanced", "importance": "required"},
            {"name": "PostgreSQL", "level": "intermediate", "importance": "required"},
            {"name": "Python", "level": "intermediate", "importance": "preferred"},
            {"name": "GraphQL", "level": "intermediate", "importance": "required"},
        ],
        "relevance": 0,
        "apply": False,
        "source": "real_graph",
    },
    "real_google_dataform": {
        "title": "Software Engineer III, Backend, Dataform",
        "company": "Google",
        "url": "https://jobs.eval.example/real/google-dataform",
        "description": (
            "Backend Software Engineer III on Dataform. Go/TypeScript/"
            "JavaScript oriented Google Cloud role — off-track vs Python PKG."
        ),
        "skills": [
            {"name": "Go", "level": "advanced", "importance": "required"},
            {"name": "TypeScript", "level": "intermediate", "importance": "required"},
            {"name": "JavaScript", "level": "intermediate", "importance": "required"},
            {"name": "Google Cloud Platform", "level": "intermediate", "importance": "required"},
        ],
        "relevance": 0,
        "apply": False,
        "source": "real_graph",
    },
    "redis_cache_api": {
        "title": "Backend Engineer Redis Caching",
        "company": "CacheWorks",
        "url": "https://jobs.eval.example/cacheworks-redis",
        "description": (
            "Python FastAPI services with Redis caching and PostgreSQL. "
            "Synthetic fixture to force a clear on-role missing skill (Redis)."
        ),
        "skills": [
            {"name": "Python", "level": "advanced", "importance": "required"},
            {"name": "FastAPI", "level": "advanced", "importance": "required"},
            {"name": "Redis", "level": "intermediate", "importance": "required"},
            {"name": "PostgreSQL", "level": "intermediate", "importance": "required"},
        ],
        "relevance": 2,
        "apply": False,
        "source": "synthetic",
    },
    "celery_worker": {
        "title": "Python Worker Engineer Celery",
        "company": "QueueLabs",
        "url": "https://jobs.eval.example/queuelabs-celery",
        "description": "Async Python workers with Celery and Redis brokers.",
        "skills": [
            {"name": "Python", "level": "advanced", "importance": "required"},
            {"name": "Celery", "level": "intermediate", "importance": "required"},
            {"name": "Redis", "level": "intermediate", "importance": "required"},
        ],
        "relevance": 1,
        "apply": False,
        "source": "synthetic",
    },
}

# Alias clusters that must collapse to one Skill node after ingest.
ER_CLUSTERS: dict[str, list[str]] = {
    "React": ["React.js", "React"],
    "Kubernetes": ["k8s", "Kubernetes"],
    "PostgreSQL": ["postgres", "PostgreSQL"],
}

# Distinct pairs that must NOT merge.
ER_MUST_STAY_APART: list[tuple[str, str]] = [
    ("Java", "JavaScript"),
    ("React", "Rust"),
    ("Go", "Python"),
]

# After ingest, person A must hold these (finished + certificate) and must
# not hold in-progress/planned-only skills.
EXPECTED_HAS_SKILL = {
    "Python",
    "FastAPI",
    "Neo4j",
    "LangChain",
    "BeautifulSoup",
    "React",
    "TypeScript",
    "Tailwind CSS",
    "Kubernetes",
    "Docker",
    "Apache Spark",
    "PostgreSQL",
    "HTML",
    "AWS",
}
MUST_NOT_HAS_SKILL = {"Flutter", "Dart", "Rust", "Qiskit", "Java", "Go", "PHP"}

# TargetRole used by skill-gap eval (scoped demand, not the whole job board).
TARGET_ROLE: dict[str, Any] = {
    "title": "Python Backend Engineer",
    "location": "Warsaw",
    "country": "Poland",
    "sample_job_keys": [
        "graphrag_role",
        "fastapi_backend",
        "real_python_ai_backend",
        "real_senior_ai",
        "real_ey_aiml",
        "redis_cache_api",
        "k8s_platform",
        "junior_py",
        "real_cognism_mlops",
        "real_tidio_ml",
    ],
}

# Exhaustive gold for gaps vs TARGET_ROLE.sample_job_keys only.
GAP_GOLD: dict[str, str] = {
    "RAG": "missing",
    "LangGraph": "missing",
    "Redis": "missing",
    "Terraform": "missing",
    "PyTorch": "missing",
    "Natural Language Processing": "missing",
    "Kubernetes": "underleveled",
}
GAP_MUST_INCLUDE = GAP_GOLD
GAP_MUST_EXCLUDE = {
    "Python",
    "FastAPI",
    "PostgreSQL",
    "Neo4j",
    "LangChain",
    "Docker",
    "Java",
    "Go",
    "PHP",
    "WordPress",
    "Spring Boot",
    "Ruby on Rails",
}

# Retrieval qrels: grades keyed by project/skill/certificate *handles*.
# Handles: project:<key>, skill:<Canonical>, cert:aws
RETRIEVAL_QUERIES: list[dict[str, Any]] = [
    {
        "id": "q_graphrag",
        "text": "Neo4j knowledge graph GraphRAG personal assistant LangChain",
        "qrels": {
            "project:graphrag": 2,
            "skill:Neo4j": 2,
            "skill:LangChain": 2,
            "project:rag_bot": 1,
            "skill:Python": 1,
            "skill:FastAPI": 1,
        },
    },
    {
        "id": "q_k8s",
        "text": "Kubernetes cluster deployment k8s production",
        "qrels": {"project:k8s": 2, "skill:Kubernetes": 2, "skill:Docker": 1},
    },
    {
        "id": "q_react",
        "text": "React TypeScript dashboard frontend hiring Kanban",
        "qrels": {
            "project:dashboard": 2,
            "skill:React": 2,
            "skill:TypeScript": 2,
            "skill:Tailwind CSS": 1,
        },
    },
    {
        "id": "q_spark",
        "text": "Apache Spark ETL data warehouse postgres pipeline",
        "qrels": {
            "project:spark": 2,
            "skill:Apache Spark": 2,
            "skill:PostgreSQL": 2,
        },
    },
    {
        "id": "q_aws",
        "text": "AWS cloud certification practitioner",
        "qrels": {"cert:aws": 2, "skill:AWS": 2},
    },
    {
        "id": "q_fastapi",
        "text": "FastAPI REST backend PostgreSQL payments API",
        "qrels": {
            "project:rest_api": 2,
            "skill:FastAPI": 2,
            "skill:PostgreSQL": 2,
            "project:graphrag": 1,
        },
    },
    {
        "id": "q_scrape",
        "text": "web scraping job board BeautifulSoup LinkedIn",
        "qrels": {"project:scraper": 2, "skill:BeautifulSoup": 2, "skill:Python": 1},
    },
    {
        "id": "q_job_graphrag",
        "text": (
            "Job title: GraphRAG Python Engineer. "
            "Skills: Python Neo4j FastAPI LangChain knowledge graph retrieval"
        ),
        "qrels": {
            "project:graphrag": 2,
            "project:rag_bot": 1,
            "skill:Neo4j": 2,
            "skill:LangChain": 1,
            "skill:Python": 1,
        },
    },
    {
        "id": "q_flutter",
        "text": "Flutter Dart mobile habit tracker app",
        "qrels": {"project:flutter": 2},
    },
    {
        "id": "q_python_course",
        "text": "beginner Python tutorial teaching site HTML",
        "qrels": {"project:tutorial": 2, "skill:Python": 1, "skill:HTML": 1},
    },
    {
        "id": "q_langchain_qa",
        "text": "LangChain PDF document question answering chatbot",
        "qrels": {"project:rag_bot": 2, "skill:LangChain": 2, "project:graphrag": 1},
    },
    {
        "id": "q_docker",
        "text": "Docker containerize API image",
        "qrels": {"skill:Docker": 2, "project:k8s": 1},
    },
    {
        "id": "q_payments",
        "text": "idempotent payments FastAPI service",
        "qrels": {"project:rest_api": 2, "skill:FastAPI": 1},
    },
    {
        "id": "q_typescript",
        "text": "TypeScript React component library",
        "qrels": {"skill:TypeScript": 2, "project:dashboard": 2, "skill:React": 1},
    },
    {
        "id": "q_job_spark",
        "text": "Job title: Data Engineer Spark. Skills: Apache Spark Python PostgreSQL",
        "qrels": {
            "project:spark": 2,
            "skill:Apache Spark": 2,
            "skill:PostgreSQL": 1,
            "skill:Python": 1,
        },
    },
    {
        "id": "q_leak",
        "text": "Secret Quantum Compiler Qiskit proprietary IR",
        "qrels": {},
        "forbidden_project": "person_b",
    },
    {
        "id": "q_neo4j_only",
        "text": "Cypher property graph Neo4j indexes",
        "qrels": {"skill:Neo4j": 2, "project:graphrag": 2},
    },
    {
        "id": "q_tailwind",
        "text": "Tailwind CSS utility classes UI",
        "qrels": {"skill:Tailwind CSS": 2, "project:dashboard": 1},
    },
    {
        "id": "q_job_frontend",
        "text": "Job title: Frontend Engineer React. Skills: React TypeScript CSS",
        "qrels": {
            "project:dashboard": 2,
            "skill:React": 2,
            "skill:TypeScript": 2,
        },
    },
    {
        "id": "q_planned_rust",
        "text": "Rust rewrite command line tool",
        "qrels": {"project:rust_plan": 2},
    },
    {
        "id": "q_html",
        "text": "HTML static tutorial website",
        "qrels": {"skill:HTML": 2, "project:tutorial": 2},
    },
    {
        "id": "q_bs4",
        "text": "BeautifulSoup HTML parser scrape",
        "qrels": {"skill:BeautifulSoup": 2, "project:scraper": 2},
    },
]

# Emails: gold classification / stage / expected Kanban effect on Acme vs Bank.
EMAILS: list[dict[str, Any]] = [
    {
        "id": "e_empty",
        "subject": "",
        "body": "",
        "sender": "nobody@example.com",
        "message_id": "<empty@eval>",
        "classification": "other",
        "application_stage": "none",
        "entity_name": "",
        "status_effect": "unchanged",
        "heuristic": True,
    },
    {
        "id": "e_newsletter",
        "subject": "Your weekly digest",
        "body": "Top stories this week.",
        "sender": "newsletter@news.example.com",
        "message_id": "<news@eval>",
        "classification": "other",
        "application_stage": "none",
        "entity_name": "",
        "status_effect": "unchanged",
        "heuristic": True,
    },
    {
        "id": "e_password",
        "subject": "Password reset",
        "body": "Click to reset your password.",
        "sender": "noreply@accounts.example.com",
        "message_id": "<pw@eval>",
        "classification": "other",
        "application_stage": "none",
        "entity_name": "",
        "status_effect": "unchanged",
        "heuristic": True,
    },
    {
        "id": "e_unsub",
        "subject": "Unsubscribe confirmation",
        "body": "You have been unsubscribed.",
        "sender": "mailer-daemon@example.com",
        "message_id": "<unsub@eval>",
        "classification": "other",
        "application_stage": "none",
        "entity_name": "",
        "status_effect": "unchanged",
        "heuristic": True,
    },
    {
        "id": "e_interview_acme",
        "subject": "Interview invitation — GraphRAG Python Engineer",
        "body": (
            "Dear Alex, we would like to invite you to interview for the "
            "GraphRAG Python Engineer role at Acme AI. Next steps attached."
        ),
        "sender": "talent@acme-ai.example",
        "message_id": "<int-acme@eval>",
        "classification": "career_related",
        "application_stage": "interview_invite",
        "entity_name": "Acme AI",
        "status_effect": "Interview",
        "heuristic": False,
    },
    {
        "id": "e_ack_acme",
        "subject": "Application received",
        "body": "Thanks for applying to Acme AI. We have received your application.",
        "sender": "jobs@acme-ai.example",
        "message_id": "<ack-acme@eval>",
        "classification": "career_related",
        "application_stage": "applied_ack",
        "entity_name": "Acme AI",
        "status_effect": "Responded",
        "heuristic": False,
    },
    {
        "id": "e_reject_bank",
        "subject": "Your application to National Bank",
        "body": (
            "We regret to inform you that your application for Java Spring "
            "Backend at National Bank has been rejected."
        ),
        "sender": "hr@national-bank.example",
        "message_id": "<rej-bank@eval>",
        "classification": "career_related",
        "application_stage": "rejection",
        "entity_name": "National Bank",
        "status_effect": "Rejected",
        "heuristic": False,
    },
    {
        "id": "e_offer_acme",
        "subject": "Offer letter from Acme AI",
        "body": "We are pleased to extend a job offer for the GraphRAG role.",
        "sender": "talent@acme-ai.example",
        "message_id": "<offer-acme@eval>",
        "classification": "career_related",
        "application_stage": "offer",
        "entity_name": "Acme AI",
        "status_effect": "Offer",
        "heuristic": False,
    },
    {
        "id": "e_assessment",
        "subject": "Coding challenge — Acme AI",
        "body": "Please complete this take-home assessment for your candidacy.",
        "sender": "hiring@acme-ai.example",
        "message_id": "<assess-acme@eval>",
        "classification": "career_related",
        "application_stage": "assessment",
        "entity_name": "Acme AI",
        "status_effect": "Interview",
        "heuristic": False,
    },
    {
        "id": "e_cold",
        "subject": "Opportunity at OtherCorp",
        "body": "Saw your profile; would you consider a new position?",
        "sender": "recruiter@othercorp.example",
        "message_id": "<cold@eval>",
        "classification": "career_related",
        "application_stage": "none",
        "entity_name": "OtherCorp",
        "status_effect": "unchanged",
        "heuristic": False,
    },
    {
        "id": "e_spam_career_words",
        "subject": "Your weekly digest",
        "body": "Unsubscribe from this newsletter about gardening.",
        "sender": "news@shop.example.com",
        "message_id": "<spam@eval>",
        "classification": "other",
        "application_stage": "none",
        "entity_name": "",
        "status_effect": "unchanged",
        "heuristic": True,
    },
    {
        "id": "e_security",
        "subject": "Security alert on your account",
        "body": "New login from unknown device.",
        "sender": "noreply@mail.example.com",
        "message_id": "<sec@eval>",
        "classification": "other",
        "application_stage": "none",
        "entity_name": "",
        "status_effect": "unchanged",
        "heuristic": True,
    },
    {
        "id": "e_interview_beta",
        "subject": "Interview invitation — Mid Backend Engineer FastAPI",
        "body": (
            "Hi Alex, Beta Labs would like to schedule an interview for the "
            "Mid Backend Engineer FastAPI role."
        ),
        "sender": "talent@beta-labs.example",
        "message_id": "<int-beta@eval>",
        "classification": "career_related",
        "application_stage": "interview_invite",
        "entity_name": "Beta Labs",
        "status_effect": "Interview",
        "heuristic": False,
    },
    {
        "id": "e_ack_beta",
        "subject": "We received your application — Beta Labs",
        "body": "Thanks for applying to Beta Labs. Your application is under review.",
        "sender": "jobs@beta-labs.example",
        "message_id": "<ack-beta@eval>",
        "classification": "career_related",
        "application_stage": "applied_ack",
        "entity_name": "Beta Labs",
        "status_effect": "Responded",
        "heuristic": False,
    },
    {
        "id": "e_reject_rivi",
        "subject": "Update on your Backend Engineer - Python AI application",
        "body": (
            "Thank you for your interest in RiVi Consulting Group L.L.C. "
            "Unfortunately we will not proceed with your candidacy."
        ),
        "sender": "hr@rivi.example",
        "message_id": "<rej-rivi@eval>",
        "classification": "career_related",
        "application_stage": "rejection",
        "entity_name": "RiVi Consulting Group L.L.C",
        "status_effect": "Rejected",
        "heuristic": False,
    },
    {
        "id": "e_assessment_beta",
        "subject": "Take-home assignment — Beta Labs",
        "body": "Please complete this FastAPI coding assessment within 5 days.",
        "sender": "hiring@beta-labs.example",
        "message_id": "<assess-beta@eval>",
        "classification": "career_related",
        "application_stage": "assessment",
        "entity_name": "Beta Labs",
        "status_effect": "Interview",
        "heuristic": False,
    },
    {
        "id": "e_promo",
        "subject": "50% off cloud credits",
        "body": "Limited time offer on compute credits. Buy now.",
        "sender": "promo@cloudshop.example.com",
        "message_id": "<promo@eval>",
        "classification": "other",
        "application_stage": "none",
        "entity_name": "",
        "status_effect": "unchanged",
        "heuristic": True,
    },
    {
        "id": "e_invoice",
        "subject": "Invoice #4421",
        "body": "Your invoice for last month is attached.",
        "sender": "billing@vendor.example.com",
        "message_id": "<inv@eval>",
        "classification": "other",
        "application_stage": "none",
        "entity_name": "",
        "status_effect": "unchanged",
        "heuristic": True,
    },
]


def job_relevance_gold() -> dict[str, int]:
    return {key: int(spec["relevance"]) for key, spec in JOBS.items()}
