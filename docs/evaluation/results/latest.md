# Evaluation results (Dataset A)

Generated: 2026-09-06T20:07:47.841575+00:00
Neo4j: `bolt://neo4j:7687`
Embedding model: `all-MiniLM-L6-v2`
LLM used: `True`

## 5.2 Functional scenarios

Task completion: **12/12** (100%)

| ID | Pass | Detail |
|---|---|---|
| UC-01 produced edges | yes | person A PRODUCED 10 projects |
| UC-01 status preserved | yes | flutter=in_progress rust=planned |
| UC-01 HAS_SKILL only finished | yes | forbidden skills on person: [] |
| UC-01 skill level monotonic | yes | Python level=expert (tutorial was beginner) |
| UC-01 alias collapse React.js | yes | React skill nodes=1 |
| UC-02 jobs in graph | yes | JobOffer count=22 |
| UC-02 REQUIRES edges | yes | REQUIRES count=82 |
| UC-02/UC-05 applications linked | yes | applications=4 |
| UC-03/UC-07 chronology | yes | employment=1 education=1 certs=1 |
| UC-06 person scope | yes | person A does not PRODUCE person B's project |
| UC-06 person B exists | yes | person B id=eval_person_b |
| UC-01 ingest extra project | yes | extra=fb46a87d-19bc-48e0-ab29-dcbcbb4d5366 python_level=expert |

## 5.3 Knowledge graph quality

- Schema completeness (labels): 0.9090909090909091
- Schema completeness (relationships): 0.8235294117647058
- HAS_SKILL F1 vs gold: 1.0
- Python level not downgraded: True (expert)
- Entity resolution pairwise correct: True
- Dirt injection detected: True

## 5.4 GraphRAG ablation (nDCG@8 / Recall@8)

| Arm | nDCG@8 | Recall@8 | Leak rate |
|---|---|---|---|
| V0 | 0.5309900058828042 | 0.4272727272727273 | 0.0 |
| V1 | 0.5309900058828042 | 0.4272727272727273 | 0.0 |
| H0 | 0.8398803185372095 | 0.8507575757575757 | 0.0 |
| H1 | 0.8398803185372095 | 0.8507575757575757 | 0.0 |

V1−V0 nDCG: 0.0
H1−H0 nDCG: 0.0
H0−V0 nDCG: 0.30889031265440525

## 5.5 Task pipelines

### Job matching (overlap)

{
  "ndcg@10": 0.8082637482547682,
  "spearman_rho": 0.5555245238960443,
  "mean_score_grade2": 79.66666666666667,
  "mean_score_grade0": 21.6,
  "ranking": [
    {
      "job_key": "graphrag_role",
      "job_id": "ec464222-16ae-459f-838d-f5cafc33bef6",
      "score": 100.0,
      "gold": 2,
      "title": "GraphRAG Python Engineer"
    },
    {
      "job_key": "fastapi_backend",
      "job_id": "db92d3ac-25c1-4cd7-8ae2-14f489d4d5b0",
      "score": 100.0,
      "gold": 2,
      "title": "Mid Backend Engineer FastAPI"
    },
    {
      "job_key": "k8s_platform",
      "job_id": "411115bd-7802-4f24-a068-3d803863ca73",
      "score": 100.0,
      "gold": 1,
      "title": "Platform Engineer Kubernetes"
    },
    {
      "job_key": "data_eng",
      "job_id": "116a827c-4dbc-43dd-9306-f9bbab886bc8",
      "score": 100.0,
      "gold": 1,
      "title": "Data Engineer Spark"
    },
    {
      "job_key": "junior_py",
      "job_id": "57988877-660d-44b9-a447-8f0b40ee386a",
      "score": 100.0,
      "gold": 1,
      "title": "Junior Python Developer"
    },
    {
      "job_key": "real_accenture_intern",
      "job_id": "ea96fafa-833f-4507-b978-2da972c01820",
      "score": 100.0,
      "gold": 1,
      "title": "AI/MLOps Internship Program"
    },
    {
      "job_key": "real_jc_agentic",
      "job_id": "04b88ece-b5e0-4d40-9556-e03e2209d07f",
      "score": 100.0,
      "gold": 1,
      "title": "Senior Data Scientist (Agentic AI Platform)"
    },
    {
      "job_key": "real_ey_aiml",
      "job_id": "0998bed6-6b5d-42a9-ba0e-34a8537bd712",
      "score": 83.0,
      "gold": 2,
      "title": "AI/ML Engineer"
    },
    {
      "job_key": "real_cognism_mlops",
      "job_id": "cea7ffd7-99e9-4430-b3cf-fe56932683a3",
      "score": 80.0,
      "gold": 1,
      "title": "MLOps Engineer"
    },
    {
      "job_key": "redis_cache_api",
      "job_id": "7128aa93-5952-49dc-b599-f15db66b9c32",
      "score": 75.0,
      "gold": 2,
      "title": "Backend Engineer Redis Caching"
    },
    {
      "job_key": "frontend",
      "job_id": "ce9a800e-5db1-4771-a0d8-34be390cad32",
      "score": 67.0,
      "gold": 1,
      "title": "Frontend Engineer React"
    },
    {
      "job_key": "real_arche_ai_py",
      "job_id": "8b258cf3-4be0-4f05-aa1b-27fe3cb6eee9",
      "score": 67.0,
      "gold": 1,
      "title": "Senior AI & Python Engineer"
    },
    {
      "job_key": "real_python_ai_backend",
      "job_id": "301e5d4d-e18f-415e-9391-7812adcb4430",
      "score": 60.0,
      "gold": 2,
      "title": "Backend Engineer - Python AI"
    },
    {
      "job_key": "real_senior_ai",
      "job_id": "5622f93c-1248-42b1-9d80-ca81f6749e75",
      "score": 60.0,
      "gold": 2,
      "title": "Senior AI Engineer"
    },
    {
      "job_key": "real_gitlab_ruby",
      "job_id": "784b418d-cacc-4935-a230-4e4bf4b9a8db",
      "score": 50.0,
      "gold": 0,
      "title": "Senior Backend Engineer (Ruby)"
    },
    {
      "job_key": "real_tidio_ml",
      "job_id": "00742c7e-5679-46cb-9313-d72a85d2cfbc",
      "score": 40.0,
      "gold": 1,
      "title": "Senior Machine Learning Engineer (NLP/LLMs)"
    },
    {
      "job_key": "go_sre",
      "job_id": "9ca29564-9d92-4bac-9de5-6c4eb99dda92",
      "score": 33.0,
      "gold": 0,
      "title": "SRE Go and Kubernetes"
    },
    {
      "job_key": "nlp",
      "job_id": "5e9bb847-cdec-44a7-9370-8f5a7f20fbd3",
      "score": 33.0,
      "gold": 1,
      "title": "NLP Research Scientist"
    },
    {
      "job_key": "celery_worker",
      "job_id": "75ec320d-f802-4a4c-bea6-1b48bb932e1c",
      "score": 33.0,
      "gold": 1,
      "title": "Python Worker Engineer Celery"
    },
    {
      "job_key": "real_google_dataform",
      "job_id": "56d162a0-2cc2-4d40-ad78-7bad5fe9193a",
      "score": 25.0,
      "gold": 0,
      "title": "Software Engineer III, Backend, Dataform"
    },
    {
      "job_key": "java_bank",
      "job_id": "37f4a213-ae09-4557-a9b4-a0e1e046d2f9",
      "score": 0.0,
  

### Skill gaps

{
  "target_role_id": "target_role_python_backend_engineer",
  "target_role_title": "Python Backend Engineer",
  "target_role_ready": true,
  "sample_status": "ready",
  "sample_job_count": 10,
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
    "real_tidio_ml"
  ],
  "raw_keys": [
    "core_strengths",
    "sample_job_count",
    "sample_status",
    "skill_gaps",
    "target_role_ready",
    "target_role_title"
  ],
  "predicted": {
    "RAG": "missing",
    "Terraform": "missing",
    "LangGraph": "missing",
    "Natural Language Processing": "missing",
    "PyTorch": "missing",
    "Redis": "missing",
    "Kubernetes": "underleveled"
  },
  "missing": {
    "precision": 1.0,
    "recall": 1.0,
    "f1": 1.0
  },
  "underleveled": {
    "precision": 1.0,
    "recall": 1.0,
    "f1": 1.0
  },
  "must_include_ok": true,
  "must_exclude_violations": [],
  "gap_count": 7,
  "analysis_excerpt": {
    "skill_gaps": [
      {
        "skill": "RAG",
        "gap_reason": "Missing skill required by 3 tracked offer(s).",
        "priority": "high",
        "kind": "missing",
        "current_level": null,
        "expected_level": "intermediate",
        "demand": 3
      },
      {
        "skill": "Terraform",
        "gap_reason": "Missing skill required by 2 tracked offer(s).",
        "priority": "high",
        "kind": "missing",
        "current_level": null,
        "expected_level": "intermediate",
        "demand": 2
      },
      {
        "skill": "LangGraph",
        "gap_reason": "Missing skill required by 2 tracked offer(s).",
        "priority": "medium",
        "kind": "missing",
        "current_level": null,
        "expected_level": "intermediate",
        "demand": 2
      },
      {
        "skill": "Natural Language Processing",
        "gap_reason": "Missing skill required by 1 tracked offer(s).",
        "priority": "medium",
        "kind": "missing",
        "current_level": null,
        "expected_level": "advanced",
        "demand": 1
      },
      {
        "skill": "PyTorch",
        "gap_reason": "Missing skill required by 1 tracked offer(s).",
        "priority": "medium",
        "kind": "missing",
        "current_level": null,
        "expected_level": "advanced",
        "demand": 1
      },
      {
        "skill": "Redis",
        "gap_reason": "Missing skill required by 1 tracked offer(s).",
        "priority": "medium",
        "kind": "missing",
        "current_level": null,
        "expected_level": "intermediate",
        "demand": 1
      },
      {
        "skill": "Kubernetes",
        "gap_reason": "Current level intermediate is below the typically expected advanced (3 tracked offer(s)).",
        "priority": "medium",
        "kind": "underleveled",
        "current_level": "intermediate",
        "expected_level": "advanced"

### Email

{
  "heuristics": {
    "classification": {
      "labels": [
        "other"
      ],
      "per_label": {
        "other": {
          "precision": 1.0,
          "recall": 1.0,
          "f1": 1.0,
          "support": 8.0
        }
      },
      "accuracy": 1.0,
      "macro_f1": 1.0,
      "n": 8
    },
    "career_mail_not_short_circuited": 10
  },
  "llm": {
    "classification": {
      "labels": [
        "career_related"
      ],
      "per_label": {
        "career_related": {
          "precision": 1.0,
          "recall": 1.0,
          "f1": 1.0,
          "support": 10.0
        }
      },
      "accuracy": 1.0,
      "macro_f1": 1.0,
      "n": 10
    },
    "application_stage": {
      "labels": [
        "applied_ack",
        "assessment",
        "interview_invite",
        "none",
        "offer",
        "rejection"
      ],
      "per_label": {
        "applied_ack": {
          "precision": 1.0,
          "recall": 1.0,
          "f1": 1.0,
          "support": 2.0
        },
        "assessment": {
          "precision": 1.0,
          "recall": 1.0,
          "f1": 1.0,
          "support": 2.0
        },
        "interview_invite": {
          "precision": 1.0,
          "recall": 1.0,
          "f1": 1.0,
          "support": 2.0
        },
        "none": {
          "precision": 1.0,
          "recall": 1.0,
          "f1": 1.0,
          "support": 1.0
        },
        "offer": {
          "precision": 1.0,
          "recall": 1.0,
          "f1": 1.0,
          "support": 1.0
        },
        "rejection": {
          "precision": 1.0,
          "recall": 1.0,
          "f1": 1.0,
          "support": 2.0
        }
      },
      "accuracy": 1.0,
      "macro_f1": 1.0,
      "n": 10
    }
  },
  "status_updates": {
    "acme": "Interview",
    "bank": "Rejected",
    "beta": "Interview",
    "rivi": "Rejected",
    "unmatched_offer_left_apps": true,
    "pass": true
  }
}

### CV

{
  "n_jobs": 4,
  "curator_ok": true,
  "grounding_ok": true,
  "llm_ran": true,
  "known_project_titles": [
    "Beginner Python Course Site",
    "Flutter Habit Tracker",
    "Hiring Dashboard",
    "Job Board Scraper",
    "Kubernetes Toy Deploy",
    "LangChain RAG Chatbot",
    "Payments REST API",
    "Personal GraphRAG Career Assistant",
    "Rust Rewrite Spike",
    "Spark ETL Warehouse"
  ],
  "per_job": [
    {
      "job_key": "graphrag_role",
      "job_id": "ec464222-16ae-459f-838d-f5cafc33bef6",
      "hit_labels": [
        "Project",
        "Skill"
      ],
      "no_joboffer_hits": true,
      "no_person_b_project": true,
      "hit_count": 8,
      "llm_ran": true,
      "budget_project_count": 4,
      "generated_project_titles": [
        "Beginner Python Course Site",
        "LangChain RAG Chatbot",
        "Payments REST API",
        "Personal GraphRAG Career Assistant"
      ],
      "invented_projects": [],
      "invented_skills": [],
      "person_b_mentioned": false,
      "headline": "Backend Engineer",
      "grounding_ok": true
    },
    {
      "job_key": "fastapi_backend",
      "job_id": "db92d3ac-25c1-4cd7-8ae2-14f489d4d5b0",
      "hit_labels": [
        "Project",
        "Skill"
      ],
      "no_joboffer_hits": true,
      "no_person_b_project": true,
      "hit_count": 8,
      "llm_ran": true,
      "budget_project_count": 4,
      "generated_project_titles": [
        "Beginner Python Course Site",
        "Hiring Dashboard",
        "Payments REST API",
        "Personal GraphRAG Career Assistant"
      ],
      "invented_projects": [],
      "invented_skills": [],
      "person_b_mentioned": false,
      "headline": "Backend Engineer FastAPI",
      "grounding_ok": true
    },
    {
      "job_key": "real_python_ai_backend",
      "job_id": "301e5d4d-e18f-415e-9391-7812adcb4430",
      "hit_labels": [
        "Project",
        "Skill"
      ],
      "no_joboffer_hits": true,
      "no_person_b_project": true,
      "hit_count": 8,
      "llm_ran": true,
      "budget_project_count": 4,
      "generated_project_titles": [
        "Beginner Python Course Site",
        "Hiring Dashboard",
        "LangChain RAG Chatbot",
        "Personal GraphRAG Career Assistant"
      ],
      "invented_projects": [],
      "invented_skills": [],
      "person_b_mentioned": false,
      "headline": "Backend Engineer - Python AI",
      "grounding_ok": true
    },
    {
      "job_key": "java_bank",
      "job_id": "37f4a213-ae09-4557-a9b4-a0e1e046d2f9",
      "hit_labels": [
        "Project"
      ],
      "no_joboffer_hits": true,
      "no_person_b_project": true,
      "hit_count": 8,
      "llm_ran": true,
      "budget_project_count": 4,
      "generated_project_titles": [
        "Hiring Dashboard",
        "Job Board Scraper",
        "Payments REST API",
        "Personal GraphRAG Career Assistant"
      ],
      "invented_projects": [],
      "invented_skills": [],
      "person_b_mentioned": false,
      "headline": "Backend Engineer",
      "grounding_ok": true
    }
  ]
}

