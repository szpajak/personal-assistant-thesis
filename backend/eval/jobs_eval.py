"""Job-ranking evaluation: overlap scores vs graded relevance (nDCG, Spearman)."""

from __future__ import annotations

from typing import Any

from eval.dataset_a import JOBS, PERSON_A, job_relevance_gold
from eval.metrics import mean, ndcg_at_k, spearman_rho

from app.kg.embeddings import KGEmbeddings
from app.kg.graphrag import GraphRAG
from app.kg.repository import KGRepository
from app.pipelines.job_match_pipeline import JobMatchPipeline


def _rank_ids(matches: list[dict[str, Any]], key: str = "match_score") -> list[str]:
    ordered = sorted(matches, key=lambda m: float(m.get(key) or 0), reverse=True)
    return [str(m.get("job_id") or m.get("id") or "") for m in ordered if m.get("job_id") or m.get("id")]


async def evaluate_jobs(
    repo: KGRepository,
    graph_rag: GraphRAG,
    id_map: dict[str, Any],
    *,
    use_llm: bool,
) -> dict[str, Any]:
    jobs: dict[str, str] = id_map["jobs"]
    gold_by_key = job_relevance_gold()
    graded = {jobs[key]: grade for key, grade in gold_by_key.items() if key in jobs}
    job_ids = list(jobs.values())

    embeddings = KGEmbeddings(kg_repository=repo)
    pipeline = JobMatchPipeline(
        kg_repository=repo, graph_rag=graph_rag, embeddings=embeddings
    )
    overlap = await pipeline.run(
        PERSON_A, job_ids=job_ids, use_llm=False, shortlist_top_k=len(job_ids)
    )
    # Normalise job_id field — pipeline may use id from the offer.
    for row in overlap:
        if not row.get("job_id") and row.get("id"):
            row["job_id"] = row["id"]

    ranked = _rank_ids(overlap)
    scores_by_id = {
        str(row.get("job_id") or row.get("id")): float(row.get("match_score") or 0)
        for row in overlap
    }
    gold_vec = [float(graded.get(jid, 0)) for jid in job_ids]
    pred_vec = [scores_by_id.get(jid, 0.0) for jid in job_ids]

    result: dict[str, Any] = {
        "n_jobs": len(job_ids),
        "overlap": {
            "ndcg@10": ndcg_at_k(ranked, graded, 10),
            "spearman_rho": spearman_rho(pred_vec, gold_vec),
            "mean_score_grade2": mean(
                scores_by_id.get(jobs[k], 0.0)
                for k, g in gold_by_key.items()
                if g == 2 and k in jobs
            ),
            "mean_score_grade0": mean(
                scores_by_id.get(jobs[k], 0.0)
                for k, g in gold_by_key.items()
                if g == 0 and k in jobs
            ),
            "ranking": [
                {
                    "job_key": next(k for k, v in jobs.items() if v == jid),
                    "job_id": jid,
                    "score": scores_by_id.get(jid, 0.0),
                    "gold": graded.get(jid, 0),
                    "title": JOBS[next(k for k, v in jobs.items() if v == jid)]["title"],
                }
                for jid in ranked
            ],
        },
        "llm_ran": False,
    }

    if use_llm:
        llm_matches = await pipeline.run(
            PERSON_A, job_ids=job_ids, use_llm=True, shortlist_top_k=min(10, len(job_ids))
        )
        for row in llm_matches:
            if not row.get("job_id") and row.get("id"):
                row["job_id"] = row["id"]
        llm_ranked = _rank_ids(llm_matches)
        llm_scores = {
            str(row.get("job_id") or row.get("id")): float(row.get("match_score") or 0)
            for row in llm_matches
        }
        llm_pred = [llm_scores.get(jid, 0.0) for jid in job_ids]
        result["llm_ran"] = True
        result["llm"] = {
            "ndcg@10": ndcg_at_k(llm_ranked, graded, 10),
            "spearman_rho": spearman_rho(llm_pred, gold_vec),
        }

    return result
