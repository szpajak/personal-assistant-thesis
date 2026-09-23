"""Skill-gap specification test against Dataset A TargetRole gold."""

from __future__ import annotations

from typing import Any

from eval.dataset_a import GAP_GOLD, GAP_MUST_EXCLUDE, PERSON_A, TARGET_ROLE
from eval.metrics import set_prf

from app.kg.graphrag import GraphRAG
from app.kg.repository import KGRepository
from app.pipelines.skill_analysis_pipeline import SkillAnalysisPipeline
from app.utils.skill_ids import resolve_canonical_skill_name


def _canon(name: str) -> str:
    return resolve_canonical_skill_name(name)


async def evaluate_skill_gaps(
    repo: KGRepository,
    graph_rag: GraphRAG,
    id_map: dict[str, Any],
) -> dict[str, Any]:
    role_id = str(id_map.get("target_role_id") or "")
    if not role_id:
        raise RuntimeError(
            "Dataset A seed did not provide target_role_id; re-seed before skills eval."
        )

    pipeline = SkillAnalysisPipeline(kg_repository=repo, graph_rag=graph_rag)
    analysis = await pipeline.run(PERSON_A, target_role_id=role_id)
    gaps = list(analysis.get("skill_gaps") or analysis.get("gaps") or [])
    if not gaps and isinstance(analysis.get("hard_gaps"), list):
        gaps = analysis["hard_gaps"]

    predicted: dict[str, str] = {}
    for gap in gaps:
        name = _canon(str(gap.get("skill") or gap.get("name") or ""))
        kind = str(gap.get("kind") or gap.get("type") or "")
        if name and kind:
            predicted[name] = kind

    # Tolerate display-name casing differences in gold keys.
    predicted_norm = {_canon(k): v for k, v in predicted.items()}
    gold_missing = {_canon(n) for n, k in GAP_GOLD.items() if k == "missing"}
    gold_under = {_canon(n) for n, k in GAP_GOLD.items() if k == "underleveled"}
    pred_missing = {n for n, k in predicted_norm.items() if k == "missing"}
    pred_under = {n for n, k in predicted_norm.items() if k == "underleveled"}

    excluded_hit = sorted(
        n for n in GAP_MUST_EXCLUDE if _canon(n) in predicted_norm
    )

    must_include_ok = all(
        predicted_norm.get(_canon(name)) == kind for name, kind in GAP_GOLD.items()
    )

    return {
        "target_role_id": role_id,
        "target_role_title": TARGET_ROLE.get("title"),
        "target_role_ready": analysis.get("target_role_ready"),
        "sample_status": analysis.get("sample_status"),
        "sample_job_count": analysis.get("sample_job_count"),
        "sample_job_keys": id_map.get("target_role_sample_keys"),
        "raw_keys": sorted(analysis.keys()),
        "predicted": predicted_norm,
        "missing": set_prf(pred_missing, gold_missing),
        "underleveled": set_prf(pred_under, gold_under),
        "must_include_ok": must_include_ok,
        "must_exclude_violations": excluded_hit,
        "gap_count": len(predicted_norm),
        "analysis_excerpt": {
            k: analysis.get(k)
            for k in ("skill_gaps", "core_strengths")
            if k in analysis
        },
    }
