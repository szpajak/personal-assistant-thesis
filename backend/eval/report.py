"""Write Chapter 5 result artefacts as JSON + Markdown."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DEFAULT_RESULTS = (
    Path(__file__).resolve().parents[2] / "docs" / "evaluation" / "results"
)
RESULTS_DIR = Path(os.environ.get("EVAL_RESULTS_DIR", str(_DEFAULT_RESULTS)))


def write_results(payload: dict[str, Any]) -> tuple[Path, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RESULTS_DIR / "latest.json"
    md_path = RESULTS_DIR / "latest.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    md_path.write_text(_to_markdown(payload), encoding="utf-8")
    return json_path, md_path


def _to_markdown(payload: dict[str, Any]) -> str:
    env = payload.get("environment") or {}
    lines = [
        "# Evaluation results (Dataset A)",
        "",
        f"Generated: {payload.get('generated_at')}",
        f"Neo4j: `{env.get('neo4j_uri')}`",
        f"Embedding model: `{env.get('embedding_model')}`",
        f"LLM used: `{payload.get('llm_used')}`",
        "",
        "## 5.2 Functional scenarios",
        "",
    ]
    scenarios = payload.get("scenarios") or {}
    lines.append(
        f"Task completion: **{scenarios.get('passed')}/{scenarios.get('n')}** "
        f"({float(scenarios.get('task_completion_rate') or 0):.0%})"
    )
    lines.append("")
    lines.append("| ID | Pass | Detail |")
    lines.append("|---|---|---|")
    for row in scenarios.get("rows") or []:
        mark = "yes" if row.get("pass") else "NO"
        lines.append(f"| {row.get('id')} | {mark} | {row.get('detail')} |")

    kg = payload.get("kg") or {}
    hs = kg.get("has_skill") or {}
    lines += [
        "",
        "## 5.3 Knowledge graph quality",
        "",
        f"- Schema completeness (labels): {kg.get('schema_completeness_labels')}",
        f"- Schema completeness (relationships): {kg.get('schema_completeness_relationships')}",
        f"- HAS_SKILL F1 vs gold: {hs.get('f1')}",
        f"- Python level not downgraded: {hs.get('python_not_downgraded')} ({hs.get('python_level')})",
        f"- Entity resolution pairwise correct: {(kg.get('entity_resolution') or {}).get('pairwise_correct')}",
        f"- Dirt injection detected: {(kg.get('consistency') or {}).get('dirt_detected')}",
        "",
        "## 5.4 GraphRAG ablation (nDCG@8 / Recall@8)",
        "",
        "| Arm | nDCG@8 | Recall@8 | Leak rate |",
        "|---|---|---|---|",
    ]
    arms = (payload.get("retrieval") or {}).get("arms") or {}
    for name in ("V0", "V1", "H0", "H1"):
        arm = arms.get(name) or {}
        lines.append(
            f"| {name} | {arm.get('ndcg@8_mean')} | {arm.get('recall@8_mean')} "
            f"| {arm.get('leak_rate')} |"
        )
    contrasts = (payload.get("retrieval") or {}).get("contrasts") or {}
    lines += [
        "",
        f"V1−V0 nDCG: {contrasts.get('V1_minus_V0_ndcg')}",
        f"H1−H0 nDCG: {contrasts.get('H1_minus_H0_ndcg')}",
        f"H0−V0 nDCG: {contrasts.get('H0_minus_V0_ndcg')}",
        "",
        "## 5.5 Task pipelines",
        "",
        "### Job matching (overlap)",
        "",
        json.dumps((payload.get("jobs") or {}).get("overlap"), indent=2, default=str)[
            :4000
        ],
        "",
        "### Skill gaps",
        "",
        json.dumps(payload.get("skills"), indent=2, default=str)[:3000],
        "",
        "### Email",
        "",
        json.dumps(payload.get("emails"), indent=2, default=str)[:3000],
        "",
        "### CV",
        "",
        json.dumps(payload.get("cv"), indent=2, default=str)[:5000],
        "",
    ]
    return "\n".join(lines) + "\n"


def utcnow() -> str:
    return datetime.now(UTC).isoformat()
