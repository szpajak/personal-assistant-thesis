# Chapter 5 evaluation kit

Offline, reproducible evaluation of the career assistant against the
protocol in the thesis (functional tests, KG quality, GraphRAG ablation,
task pipelines). **Dataset A** is an enlarged labelled fixture (synthetic
structure + real job postings adapted from the author’s graph). A separate
Dataset B episode is optional, not required.

## What you must do vs what the harness does

### You do these (cannot be invented)

1. **Dataset A is ready to run**, but you should **verify preliminary job
   grades** in `JOB_GRADES.md` (edit `relevance` in
   `backend/eval/dataset_a.py` if needed). The fixture mixes synthetic
   offers with real titles/companies from a Neo4j export
   (`real_jobs_snapshot.json`); skill lists on real rows are curated.
2. **Optional later:** rate generated CVs (1–5) and/or add more real
   emails; a separate Dataset B episode is not required if A stays the
   single enlarged fixture.
3. **DeepSeek key** comes from the **repo-root** `.env` (same file
   `make dev` / docker-compose use). `make eval` passes it with
   `--env-file .env`. Retrieval, KG constraints, overlap matching, and
   skill-gap diffs do **not** need it.
4. **Do not run this against your daily Neo4j on port 7687.** The harness
   refuses to wipe that instance. `make eval` starts an isolated Compose
   project (`personal-assistant-eval`) from `docker-compose.test.yml`
   so Dataset A never shares the daily `neo4j_data` volume.

### The harness does these

Seed Dataset A through real `KGIngestion` + embeddings; Cypher
constraint suite; UC scenario matrix; 2×2 GraphRAG ablation
(vector vs hybrid × hops 0 vs 1); job ranking vs gold; skill-gap F1;
email heuristics + optional LLM; CV deterministic checks + optional
generation.

## Run

```bash
# from repo root — starts test Neo4j/Postgres/Redis if needed
make eval
```

Phases: `seed`, `kg`, `scenarios`, `retrieve`, `jobs`, `skills`,
`emails`, `cv`, `all`.

```bash
make eval ARGS="--phase retrieve"
```

Results: `docs/evaluation/results/latest.json` and `latest.md`.

## Environment

Pinned for the thesis table: Neo4j 5.14, MiniLM `all-MiniLM-L6-v2`
(384-d cosine), GraphRAG `top_k=8`, RRF k=60, DeepSeek
`deepseek-v4-flash` temperature 0 when used. First seed downloads
MiniLM if it is not cached.
