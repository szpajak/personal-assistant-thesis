"""GraphRAG ablation: vector vs hybrid × hops 0 vs 1 (Cranfield nDCG/Recall)."""

from __future__ import annotations

from typing import Any

from eval.dataset_a import PERSON_A, RETRIEVAL_QUERIES
from eval.metrics import mean, mrr, ndcg_at_k, paired_wilcoxon_p, precision_at_k, recall_at_k, stdev

from app.kg.graphrag import GraphRAG

TOP_K = 8
LABELS = ["Project", "Skill", "Certificate"]

ARMS = (
    ("V0", {"hybrid": False, "hops": 0}),
    ("V1", {"hybrid": False, "hops": 1}),
    ("H0", {"hybrid": True, "hops": 0}),
    ("H1", {"hybrid": True, "hops": 1}),
)


def _hit_id(item: dict[str, Any]) -> str:
    node = item.get("node") or {}
    return str(node.get("id") or "")


def _resolve_qrels(
    raw: dict[str, int],
    handles: dict[str, str],
) -> dict[str, int]:
    graded: dict[str, int] = {}
    for handle, grade in raw.items():
        node_id = handles.get(handle)
        if node_id:
            graded[node_id] = int(grade)
    return graded


async def evaluate_retrieval(
    graph_rag: GraphRAG,
    id_map: dict[str, Any],
) -> dict[str, Any]:
    handles: dict[str, str] = id_map["handles"]
    forbidden = handles.get("project:person_b")
    per_arm: dict[str, list[dict[str, Any]]] = {name: [] for name, _ in ARMS}

    for query in RETRIEVAL_QUERIES:
        graded = _resolve_qrels(query["qrels"], handles)
        relevant = {nid for nid, g in graded.items() if g >= 1}
        for arm_name, params in ARMS:
            hits = await graph_rag.retrieve(
                query["text"],
                top_k=TOP_K,
                hops=int(params["hops"]),
                person_id=PERSON_A,
                label_preset="cv",
                labels=LABELS,
                hybrid=bool(params["hybrid"]),
            )
            retrieved = [_hit_id(h) for h in hits if _hit_id(h)]
            hop_ids: list[str] = []
            for hit in hits:
                for rel in hit.get("related") or []:
                    nid = str((rel.get("node") or {}).get("id") or "")
                    if nid:
                        hop_ids.append(nid)
            leak = forbidden in retrieved if forbidden else False
            hop_relevant = [nid for nid in hop_ids if nid in relevant]
            per_arm[arm_name].append(
                {
                    "query_id": query["id"],
                    "retrieved": retrieved,
                    "ndcg": ndcg_at_k(retrieved, graded, TOP_K),
                    "recall": recall_at_k(retrieved, relevant, TOP_K),
                    "precision": precision_at_k(retrieved, relevant, TOP_K),
                    "mrr": mrr(retrieved, relevant),
                    "leak_person_b": leak,
                    "hop_count": len(hop_ids),
                    "hop_precision": (
                        len(hop_relevant) / len(hop_ids) if hop_ids else 0.0
                    ),
                }
            )

    summary: dict[str, Any] = {}
    for arm_name, rows in per_arm.items():
        ndcgs = [r["ndcg"] for r in rows]
        recalls = [r["recall"] for r in rows]
        summary[arm_name] = {
            "ndcg@8_mean": mean(ndcgs),
            "ndcg@8_std": stdev(ndcgs),
            "recall@8_mean": mean(recalls),
            "precision@8_mean": mean(r["precision"] for r in rows),
            "mrr_mean": mean(r["mrr"] for r in rows),
            "leak_rate": mean(1.0 if r["leak_person_b"] else 0.0 for r in rows),
            "hop_precision_mean": mean(r["hop_precision"] for r in rows),
            "n": len(rows),
        }

    def _col(arm: str, key: str) -> list[float]:
        return [float(r[key]) for r in per_arm[arm]]

    contrasts = {
        "V1_minus_V0_ndcg": mean(_col("V1", "ndcg")) - mean(_col("V0", "ndcg")),
        "H1_minus_H0_ndcg": mean(_col("H1", "ndcg")) - mean(_col("H0", "ndcg")),
        "H0_minus_V0_ndcg": mean(_col("H0", "ndcg")) - mean(_col("V0", "ndcg")),
        "wilcoxon_p_V0_V1": paired_wilcoxon_p(_col("V0", "ndcg"), _col("V1", "ndcg")),
        "wilcoxon_p_H0_H1": paired_wilcoxon_p(_col("H0", "ndcg"), _col("H1", "ndcg")),
    }
    return {
        "top_k": TOP_K,
        "arms": summary,
        "contrasts": contrasts,
        "per_query": {name: rows for name, rows in per_arm.items()},
    }
