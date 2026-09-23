# Evaluation plan — execution tracker

## Status

| Phase | Owner | Status |
|---|---|---|
| Eval harness + Dataset A + codebook | Agent | **Done** |
| Start test Neo4j + run Dataset A (skip-LLM) | Agent | **Done** — see `results/latest.md` |
| Dataset A with DeepSeek (CV + LLM email + LLM match) | Agent | Optional (`make eval`) |
| Verify / edit preliminary job grades (`JOB_GRADES.md`) | **You** | Waiting |
| Thesis Chapter 5 write-up in `docs/thesis.tex` | Agent | **Done** |

## Dataset A headline (skip-LLM run)

- UC scenarios: **12/12**
- HAS_SKILL F1 vs gold: **1.0**; alias ER: **pass**; dirt detection: **pass**
- GraphRAG: hybrid RRF (**H0/H1 nDCG@8 ≈ 0.84**) beats vector-only (**V0/V1 ≈ 0.53**); hop 0 vs 1 did **not** change seed-node nDCG (expansion affects neighbours, not the ranked seed list). Hop neighbour precision ≈ 0.10–0.15 when hops=1.
- Job overlap ranking: **nDCG@10 ≈ 0.997**, Spearman **≈ 0.81**
- Skill-gap must-include gold: **pass**; underleveled F1 **1.0**
  (now role-scoped via Dataset A ``TargetRole``; re-run ``make eval``)
- Email heuristics + status write path: **pass**; LLM email/CV not run in this pass

## LLM phases

`make eval` now loads the **repo-root** `.env` (same as `make dev`). Earlier 401s
came from using `backend/.env`, which still had a placeholder key ending in
`_KEY`, while the working key lives in `.env` at the repo root.

```bash
make eval
```

Re-run for CV generation, LLM email classification, and LLM job rescoring.

## What you need to do

1. **Verify job grades** in `JOB_GRADES.md` / `dataset_a.py` `JOBS[*].relevance`.
2. Re-run `make eval` after edits.
3. Optional: human CV usefulness ratings for the thesis discussion.

## Commands

```bash
make eval                              # Dockerized full Dataset A
make eval ARGS="--skip-llm"            # no DeepSeek
make eval ARGS="--phase retrieve"
```

Host Windows Python often crashes on MiniLM (`OPENSSL_Applink`); `make eval` therefore runs inside `personal-assistant-backend:latest`.
