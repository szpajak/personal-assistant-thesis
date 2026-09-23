"""Seed Dataset A into the evaluation Neo4j via real ingestion + embeddings."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from eval.dataset_a import (
    CERTIFICATE,
    EDUCATION,
    EMPLOYMENT,
    JOBS,
    PERSON_A,
    PERSON_A_PROFILE,
    PERSON_B,
    PERSON_B_PROJECT,
    PROJECTS,
    TARGET_ROLE,
)
from setup_kg import setup_fulltext_indexes, setup_indexes, setup_schema

from app.kg.embeddings import KGEmbeddings
from app.kg.ingestion import KGIngestion
from app.kg.repository import KGRepository
from app.utils.skill_ids import canonical_skill_id, resolve_canonical_skill_name

CONSTRAINTS = [
    "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT project_id IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT skill_id IF NOT EXISTS FOR (s:Skill) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT job_offer_id IF NOT EXISTS FOR (j:JobOffer) REQUIRE j.id IS UNIQUE",
    "CREATE CONSTRAINT job_offer_url IF NOT EXISTS FOR (j:JobOffer) REQUIRE j.url IS UNIQUE",
    "CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT application_id IF NOT EXISTS FOR (a:Application) REQUIRE a.id IS UNIQUE",
    "CREATE CONSTRAINT email_id IF NOT EXISTS FOR (e:Email) REQUIRE e.id IS UNIQUE",
    "CREATE CONSTRAINT certificate_id IF NOT EXISTS FOR (c:Certificate) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT employment_id IF NOT EXISTS FOR (e:Employment) REQUIRE e.id IS UNIQUE",
    "CREATE CONSTRAINT education_id IF NOT EXISTS FOR (e:Education) REQUIRE e.id IS UNIQUE",
]


def assert_eval_uri(uri: str, *, force: bool = False) -> None:
    """Refuse to wipe the developer's daily Neo4j (host port 7687)."""
    if force:
        return
    # Container-internal ``bolt://neo4j:7687`` is fine; only block the host
    # mapping that points at the daily compose stack.
    if "localhost:7687" in uri or "127.0.0.1:7687" in uri:
        raise SystemExit(
            "Refusing to wipe Neo4j on localhost:7687 (daily instance). "
            "Start docker-compose.test.yml and use bolt://localhost:7688, "
            "or pass --force-db / set EVAL_NEO4J_URI for the test network."
        )


async def _wipe(repo: KGRepository) -> None:
    await repo.query("MATCH (n) DETACH DELETE n")


async def _ensure_schema(repo: KGRepository) -> None:
    for cypher in CONSTRAINTS:
        try:
            await repo.query(cypher)
        except Exception:
            pass
    await setup_indexes(repo)
    await setup_fulltext_indexes(repo)
    await setup_schema(repo)


async def _ingest_project(
    ingestion: KGIngestion,
    repo: KGRepository,
    person_id: str,
    spec: dict[str, Any],
) -> str:
    project_id = await ingestion.ingest_project(
        title=str(spec["title"]),
        description=str(spec["description"]),
        tech_stack=list(spec["tech_stack"]),
        metadata={
            "start_date": spec.get("start_date"),
            "end_date": spec.get("end_date"),
            "seniority": spec.get("seniority"),
            "achievements": spec.get("achievements") or [],
            "status": spec.get("status") or "finished",
            "source": "form",
        },
        person_id=person_id,
        skills=list(spec.get("skills") or []),
    )
    await repo.upsert_relationship(
        "Person", person_id, "PRODUCED", "Project", project_id
    )
    if str(spec.get("status") or "finished") == "finished":
        await repo.ensure_has_skill_for_finished_projects(
            person_id=person_id, project_id=project_id
        )
    return project_id


async def seed_dataset_a(*, force: bool = False) -> dict[str, Any]:
    """Wipe the eval store and ingest Dataset A. Returns an id map."""
    from app.config import settings

    assert_eval_uri(settings.neo4j_uri, force=force)
    repo = KGRepository()
    embeddings = KGEmbeddings(kg_repository=repo)
    ingestion = KGIngestion(kg_repository=repo, embeddings=embeddings)

    await _wipe(repo)
    await _ensure_schema(repo)

    # Company industry enrichment is best-effort LLM; keep Dataset A offline
    # and deterministic during seed.
    async def _no_company_llm(company: str, description: str) -> tuple[str, str]:
        return "", ""

    ingestion._infer_company_details = _no_company_llm  # type: ignore[method-assign]

    await repo.upsert_node("Person", dict(PERSON_A_PROFILE))
    await repo.upsert_node(
        "Person",
        {
            "id": PERSON_B,
            "name": "Blake Other",
            "email": "blake.eval@example.com",
        },
    )

    await ingestion.ingest_education(person_id=PERSON_A, **EDUCATION)
    await ingestion.ingest_employment(person_id=PERSON_A, **EMPLOYMENT)

    projects: dict[str, str] = {}
    for key, spec in PROJECTS.items():
        projects[key] = await _ingest_project(ingestion, repo, PERSON_A, spec)
    projects["person_b"] = await _ingest_project(
        ingestion, repo, PERSON_B, PERSON_B_PROJECT
    )

    cert_id = await ingestion.ingest_certificate(
        title=CERTIFICATE["title"],
        issuer=CERTIFICATE["issuer"],
        issued_at=CERTIFICATE["issued_at"],
        document_url=CERTIFICATE["document_url"],
        person_id=PERSON_A,
        validated_skills=list(CERTIFICATE["validated_skills"]),
    )

    jobs: dict[str, str] = {}
    for key, spec in JOBS.items():
        names = [str(s["name"]) for s in spec["skills"]]
        job_id = await ingestion.ingest_job_offer(
            title=str(spec["title"]),
            company=str(spec["company"]),
            description=str(spec["description"]),
            required_skills=names,
            metadata={
                "url": spec["url"],
                "location": "Warsaw",
                "source": "eval",
            },
            extract_skills=False,
        )
        await ingestion._link_required_skills(job_id, list(spec["skills"]))
        await repo.upsert_relationship(
            "Person", PERSON_A, "SAVED", "JobOffer", job_id
        )
        jobs[key] = job_id

    applications: dict[str, str] = {}
    now = datetime.now(UTC).isoformat()
    for job_key in (
        "graphrag_role",
        "java_bank",
        "fastapi_backend",
        "real_python_ai_backend",
    ):
        if job_key not in jobs:
            continue
        app_id = f"eval_app_{job_key}"
        await repo.upsert_node(
            "Application",
            {"id": app_id, "status": "Applied", "applied_at": now, "notes": ""},
        )
        await repo.upsert_relationship(
            "Person", PERSON_A, "APPLIED_TO", "Application", app_id
        )
        await repo.upsert_relationship(
            "Application", app_id, "FOR_OFFER", "JobOffer", jobs[job_key]
        )
        applications[job_key] = app_id

    # Role-scoped market sample (same path as production TargetRole refresh).
    role_id = await ingestion.ingest_target_role(
        person_id=PERSON_A,
        title=str(TARGET_ROLE["title"]),
        location=str(TARGET_ROLE.get("location") or ""),
        country=str(TARGET_ROLE.get("country") or ""),
    )
    sample_keys = [str(k) for k in TARGET_ROLE["sample_job_keys"]]
    sample_job_ids = [jobs[key] for key in sample_keys if key in jobs]
    await ingestion.replace_target_role_sample(role_id, sample_job_ids)
    stats = await repo.get_target_role_sample_stats(role_id)
    top_skills = [str(row["name"]) for row in stats[:15] if row.get("name")]
    await ingestion.set_target_role_required_skills(role_id, top_skills)
    await repo.upsert_node(
        "TargetRole",
        {
            "id": role_id,
            "sample_status": "ready",
            "sample_job_count": len(sample_job_ids),
            "last_sampled_at": now,
        },
    )

    skills: dict[str, str] = {}
    rows = await repo.get_person_skills(PERSON_A)
    for row in rows:
        name = resolve_canonical_skill_name(str(row.get("name") or ""))
        if name:
            skills[name] = str(row.get("id") or canonical_skill_id(name))

    return {
        "person_id": PERSON_A,
        "person_b": PERSON_B,
        "projects": projects,
        "jobs": jobs,
        "applications": applications,
        "target_role_id": role_id,
        "target_role_sample_keys": sample_keys,
        "certificate": cert_id,
        "skills": skills,
        "handles": {
            **{f"project:{k}": v for k, v in projects.items()},
            **{f"skill:{k}": v for k, v in skills.items()},
            "cert:aws": cert_id,
        },
    }
