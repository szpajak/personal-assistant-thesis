# Dataset A job grades (preliminary — please verify)

Person narrative: mid Python / GraphRAG backend engineer (Neo4j, FastAPI,
LangChain; beginner Kubernetes; some React). Grades follow
`codebook.md` (0 / 1 / 2). **Edit `relevance` in
`backend/eval/dataset_a.py` → `JOBS` if you disagree.**

Real-graph rows (`source: real_graph`) were adapted from a read-only export
of the author’s Neo4j (`docs/evaluation/real_jobs_snapshot.json`): public
titles/companies/descriptions; **skill lists curated** for stable TargetRole
gap gold (not the full extractor dump).

| Key | Title | Company | Grade | Rationale (preliminary) |
|-----|--------|---------|------:|-------------------------|
| graphrag_role | GraphRAG Python Engineer | Acme AI | **2** | Exact stack / narrative match |
| fastapi_backend | Mid Backend Engineer FastAPI | Beta Labs | **2** | Core Python/FastAPI/Postgres |
| redis_cache_api | Backend Engineer Redis Caching | CacheWorks | **2** | On-role backend; Redis gap |
| real_python_ai_backend | Backend Engineer - Python AI | RiVi Consulting | **2** | FastAPI + LangChain/LangGraph/RAG |
| real_senior_ai | Senior AI Engineer | First Advantage | **2** | Python/FastAPI/RAG/Docker |
| real_ey_aiml | AI/ML Engineer | EY | **2** | FastAPI + LangChain/LangGraph; K8s stretch |
| k8s_platform | Platform Engineer Kubernetes | CloudCo | **1** | Partial; K8s underleveled |
| data_eng | Data Engineer Spark | DataCorp | **1** | Python/Spark transferable |
| frontend | Frontend Engineer React | Webify | **1** | Has React; wrong focus |
| nlp | NLP Research Scientist | Lab AI | **1** | Python only; research ML |
| junior_py | Junior Python Developer | Startup Hub | **1** | Stack fit; too junior |
| real_tidio_ml | Senior ML Engineer (NLP/LLMs) | Tidio | **1** | FastAPI/RAG but PyTorch/NLP heavy |
| real_cognism_mlops | MLOps Engineer | Cognism | **1** | Ops/K8s/Terraform heavy |
| real_accenture_intern | AI/MLOps Internship | Accenture | **1** | Stack overlap; internship bar |
| real_arche_ai_py | Senior AI & Python Engineer | ARCHE | **1** | Python/AWS/ML consulting |
| real_jc_agentic | Senior DS (Agentic AI) | Johnson Controls | **1** | Eng overlap; DS title |
| celery_worker | Python Worker Celery | QueueLabs | **1** | Python workers; Celery/Redis |
| java_bank | Java Spring Backend | National Bank | **0** | Wrong stack |
| php | WordPress PHP Developer | Agency Nine | **0** | Wrong stack |
| go_sre | SRE Go and Kubernetes | Infra LLC | **0** | Go primary |
| real_gitlab_ruby | Senior Backend (Ruby) | GitLab Inc | **0** | Ruby primary |
| real_google_dataform | SWE III Backend Dataform | Google | **0** | Go/TS/JS |

Counts: **6× grade 2**, **11× grade 1**, **5× grade 0** (22 jobs).

## TargetRole sample (skill-gap eval)

`Python Backend Engineer` samples 10 on-role keys (see `TARGET_ROLE` in
`dataset_a.py`). Expected gaps (`GAP_GOLD`): RAG, LangGraph, Redis,
Terraform, PyTorch, NLP missing; Kubernetes underleveled.

## After you edit grades

```bash
make eval
```
