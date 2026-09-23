"""CV pipeline checks: GraphRAG curator constraints, optional generation."""

from __future__ import annotations

from typing import Any

from app.kg.graphrag import GraphRAG
from app.kg.repository import KGRepository
from app.pipelines.cv_pipeline import _CV_RETRIEVAL_LABELS, CVPipeline
from eval.dataset_a import PERSON_A, PROJECTS


def _titles(items: list[dict[str, Any]]) -> set[str]:
    return {str(p.get("title") or "").strip() for p in items if p.get("title")}


# Multiple target jobs: strong fits + one off-track offer.
_CV_JOB_KEYS = (
    "graphrag_role",
    "fastapi_backend",
    "real_python_ai_backend",
    "java_bank",
)


async def evaluate_cv(
    repo: KGRepository,
    graph_rag: GraphRAG,
    id_map: dict[str, Any],
    *,
    use_llm: bool,
) -> dict[str, Any]:
    jobs: dict[str, str] = id_map["jobs"]
    pipeline = CVPipeline(kg_repository=repo, graph_rag=graph_rag)
    leak_b = id_map["projects"].get("person_b")
    per_job: list[dict[str, Any]] = []

    for key in _CV_JOB_KEYS:
        job_id = jobs.get(key)
        if not job_id:
            continue
        job = await repo.get_node("JobOffer", job_id) or {}
        hits = await graph_rag.retrieve(
            f"Job title: {job.get('title')}\nDescription: {job.get('description')}",
            top_k=8,
            hops=1,
            person_id=PERSON_A,
            label_preset="cv",
            labels=_CV_RETRIEVAL_LABELS,
            hybrid=True,
        )
        hit_labels = {str(h.get("label")) for h in hits}
        retrieved_ids = {(h.get("node") or {}).get("id") for h in hits}
        row: dict[str, Any] = {
            "job_key": key,
            "job_id": job_id,
            "hit_labels": sorted(hit_labels),
            "no_joboffer_hits": "JobOffer" not in hit_labels,
            "no_person_b_project": leak_b not in retrieved_ids,
            "hit_count": len(hits),
            "llm_ran": False,
        }

        if use_llm:
            try:
                generated = await pipeline.run(PERSON_A, job_id)
            except Exception as exc:  # noqa: BLE001
                row["llm_error"] = str(exc)
                per_job.append(row)
                continue

            budget_projects = list(generated.get("projects") or [])
            gen = generated.get("generated") or {}
            gen_project_titles = _titles(list(gen.get("projects") or []))
            allowed = _titles(budget_projects)
            invented = sorted(t for t in gen_project_titles if t and t not in allowed)
            mention_person_b = "Secret Quantum Compiler" in str(gen)

            skills_flat: list[str] = []
            for names in (gen.get("skill_categories") or {}).values():
                if isinstance(names, list):
                    skills_flat.extend(str(n) for n in names)
            forbidden = {"Java", "Qiskit", "PHP", "WordPress", "Ruby on Rails"}
            invented_skills = sorted({s for s in skills_flat if s in forbidden})

            row.update(
                {
                    "llm_ran": True,
                    "budget_project_count": len(budget_projects),
                    "generated_project_titles": sorted(gen_project_titles),
                    "invented_projects": invented,
                    "invented_skills": invented_skills,
                    "person_b_mentioned": mention_person_b,
                    "headline": gen.get("headline"),
                    "grounding_ok": (
                        not invented and not invented_skills and not mention_person_b
                    ),
                }
            )
        per_job.append(row)

    all_titles = {spec["title"] for spec in PROJECTS.values()}
    curator_ok = all(
        r.get("no_joboffer_hits") and r.get("no_person_b_project") for r in per_job
    )
    llm_rows = [r for r in per_job if r.get("llm_ran")]
    grounding_ok = all(r.get("grounding_ok") for r in llm_rows) if llm_rows else None

    return {
        "n_jobs": len(per_job),
        "curator_ok": curator_ok,
        "grounding_ok": grounding_ok,
        "llm_ran": bool(llm_rows),
        "known_project_titles": sorted(all_titles),
        "per_job": per_job,
    }
