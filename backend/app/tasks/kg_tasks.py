"""Celery background tasks for knowledge graph maintenance."""

from __future__ import annotations

import asyncio
import logging

from ..core.celery_app import celery_app
from ..kg.repository import KGRepository

logger = logging.getLogger(__name__)


async def _run_consistency_checks(repo: KGRepository) -> None:
    logger.info("Starting KG consistency checks...")

    # 1. Check for orphaned Skill nodes (not connected to any Person, Project, or JobOffer)
    orphaned_skills_query = """
    MATCH (s:Skill)
    WHERE NOT (s)--()
    RETURN count(s) as count
    """
    results = await repo.query(orphaned_skills_query)
    orphaned_count = results[0]["count"] if results else 0
    if orphaned_count > 0:
        logger.warning(f"Found {orphaned_count} orphaned Skill nodes")
        # In production, we might want to auto-delete them or flag them
        # await repo.query("MATCH (s:Skill) WHERE NOT (s)--() DETACH DELETE s")

    # 2. Ensure all Projects have a link to a Person
    project_owner_query = """
    MATCH (p:Project)
    WHERE NOT (p)<-[:PRODUCED]-(:Person)
    RETURN count(p) as count
    """
    results = await repo.query(project_owner_query)
    unowned_projects = results[0]["count"] if results else 0
    if unowned_projects > 0:
        logger.error(f"Found {unowned_projects} Project nodes without an owner!")

    logger.info("KG consistency checks completed successfully")


@celery_app.task  # type: ignore[untyped-decorator]
def run_kg_consistency_checks() -> None:
    """Run consistency checks on the knowledge graph.

    Wrapped in ``asyncio.run`` (matching every other Celery task in this
    codebase - see ``tasks/email_tasks.py``) since Celery workers call tasks
    synchronously and would otherwise just return an un-awaited coroutine
    without ever running the checks.
    """
    repo = KGRepository()
    try:
        asyncio.run(_run_consistency_checks(repo))
    except Exception as e:
        logger.error(f"KG consistency checks failed: {e}")
        raise


@celery_app.task  # type: ignore[untyped-decorator]
def record_skill_demand_snapshot() -> None:
    """Nightly job: snapshot today's per-skill market demand (count of career
    JobOffers requiring each skill) so demand trends over time - not just the
    current live count - become queryable (``KGRepository.get_skill_demand_history``).
    """
    repo = KGRepository()
    try:
        count = asyncio.run(repo.record_skill_demand_snapshot())
        logger.info(f"Recorded skill demand snapshots for {count} skills")
    except Exception as e:
        logger.error(f"Skill demand snapshot task failed: {e}")
        raise


@celery_app.task  # type: ignore[untyped-decorator]
def merge_duplicate_skills(similarity_threshold: float = 0.93) -> None:
    """Periodic job: find Skill pairs the static alias table
    (``utils.skill_ids.SKILL_ALIASES``) didn't catch but whose embeddings are
    near-identical, and auto-merge them.

    Conservative by design: only merges pairs above a high cosine similarity
    threshold, since this is an irreversible structural change to the graph
    (all incoming/outgoing edges are repointed - see
    ``KGRepository.merge_skill_nodes``).
    """
    repo = KGRepository()

    async def _run() -> int:
        pairs = await repo.find_near_duplicate_skills(similarity_threshold)
        merged = 0
        for pair in pairs:
            try:
                await repo.merge_skill_nodes(
                    source_id=pair["source_id"], target_id=pair["target_id"]
                )
                logger.info(
                    "Merged near-duplicate skill %r (%s) into %r (%s), similarity=%.4f",
                    pair["source_name"],
                    pair["source_id"],
                    pair["target_name"],
                    pair["target_id"],
                    pair["similarity"],
                )
                merged += 1
            except Exception as exc:
                logger.warning(
                    "Failed to merge skill %s into %s: %s",
                    pair["source_id"],
                    pair["target_id"],
                    exc,
                )
        return merged

    try:
        merged_count = asyncio.run(_run())
        logger.info(f"Skill near-duplicate merge task finished: {merged_count} merges")
    except Exception as e:
        logger.error(f"Skill near-duplicate merge task failed: {e}")
        raise
