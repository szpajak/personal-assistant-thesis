"""CLI: seed Dataset A and run Chapter 5 evaluation phases."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Any

from eval import _bootstrap  # noqa: F401  — pin eval Neo4j before app imports

from eval.constraints import evaluate_kg_quality
from eval.cv_eval import evaluate_cv
from eval.emails_eval import evaluate_emails
from eval.jobs_eval import evaluate_jobs
from eval.report import utcnow, write_results
from eval.retrieve_eval import evaluate_retrieval
from eval.scenarios import run_scenarios
from eval.seed import seed_dataset_a
from eval.skills_eval import evaluate_skill_gaps

from app.config import settings
from app.kg.embeddings import KGEmbeddings
from app.kg.graphrag import GraphRAG
from app.kg.repository import KGRepository

logger = logging.getLogger("eval")

PHASES = (
    "seed",
    "kg",
    "scenarios",
    "retrieve",
    "jobs",
    "skills",
    "emails",
    "cv",
    "all",
)


def _llm_enabled() -> bool:
    key = (settings.deepseek_api_key or "").strip()
    return bool(key) and key not in {"ds-eval-missing", "ds-test", "sk-test"}


async def _run(phase: str, *, force_db: bool, skip_llm: bool) -> dict[str, Any]:
    use_llm = _llm_enabled() and not skip_llm
    repo = KGRepository()
    embeddings = KGEmbeddings(kg_repository=repo)
    graph_rag = GraphRAG(kg_repository=repo, embeddings=embeddings)

    payload: dict[str, Any] = {
        "generated_at": utcnow(),
        "phase": phase,
        "llm_used": use_llm,
        "environment": {
            "neo4j_uri": settings.neo4j_uri,
            "embedding_model": settings.huggingface_embedding_model,
            "chat_model": settings.deepseek_chat_model,
        },
    }

    need_seed = phase in {"seed", "all"} or phase != "seed"
    id_map: dict[str, Any]
    if phase == "seed" or phase == "all":
        logger.info("Seeding Dataset A into %s", settings.neo4j_uri)
        id_map = await seed_dataset_a(force=force_db)
        payload["id_map"] = {
            "person_id": id_map["person_id"],
            "projects": id_map["projects"],
            "jobs": id_map["jobs"],
            "applications": id_map["applications"],
            "certificate": id_map["certificate"],
            "skills": id_map["skills"],
        }
    elif need_seed:
        # Later phases assume a previous --phase seed in this process; re-seed
        # so each invocation is self-contained.
        id_map = await seed_dataset_a(force=force_db)
        payload["id_map"] = {
            "person_id": id_map["person_id"],
            "projects": id_map["projects"],
            "jobs": id_map["jobs"],
        }
    else:
        id_map = {}

    if phase in {"kg", "all"}:
        payload["kg"] = await evaluate_kg_quality(repo, id_map)
    if phase in {"scenarios", "all"}:
        payload["scenarios"] = await run_scenarios(repo, id_map)
    if phase in {"retrieve", "all"}:
        payload["retrieval"] = await evaluate_retrieval(graph_rag, id_map)
    if phase in {"jobs", "all"}:
        payload["jobs"] = await evaluate_jobs(
            repo, graph_rag, id_map, use_llm=use_llm
        )
    if phase in {"skills", "all"}:
        payload["skills"] = await evaluate_skill_gaps(repo, graph_rag, id_map)
    if phase in {"emails", "all"}:
        payload["emails"] = await evaluate_emails(repo, id_map, use_llm=use_llm)
    if phase in {"cv", "all"}:
        payload["cv"] = await evaluate_cv(
            repo, graph_rag, id_map, use_llm=use_llm
        )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Career-assistant thesis evaluation")
    parser.add_argument("--phase", choices=PHASES, default="all")
    parser.add_argument(
        "--force-db",
        action="store_true",
        help="Allow wiping Neo4j even on port 7687 (dangerous).",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip DeepSeek calls (CV generation, LLM job match, LLM email).",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    payload = asyncio.run(
        _run(args.phase, force_db=args.force_db, skip_llm=args.skip_llm)
    )
    json_path, md_path = write_results(payload)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    scenarios = payload.get("scenarios") or {}
    if scenarios and scenarios.get("failed"):
        print(f"Scenario failures: {scenarios['failed']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
