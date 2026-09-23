"""Use-case scenario matrix (UC-01..UC-07) against the seeded graph."""

from __future__ import annotations

from typing import Any

from eval.dataset_a import MUST_NOT_HAS_SKILL, PERSON_A, PERSON_B

from app.kg.embeddings import KGEmbeddings
from app.kg.ingestion import KGIngestion
from app.kg.repository import KGRepository
from app.utils.skill_ids import resolve_canonical_skill_name


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"id": name, "pass": passed, "detail": detail}


async def run_scenarios(
    repo: KGRepository,
    id_map: dict[str, Any],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    person = PERSON_A
    projects: dict[str, str] = id_map["projects"]
    jobs: dict[str, str] = id_map["jobs"]

    produced = await repo.query(
        "MATCH (p:Person {id: $pid})-[:PRODUCED]->(pr:Project) "
        "RETURN count(pr) AS c",
        {"pid": person},
    )
    rows.append(
        _check(
            "UC-01 produced edges",
            int(produced[0]["c"]) >= 8,
            f"person A PRODUCED {produced[0]['c']} projects",
        )
    )

    flutter = await repo.get_node("Project", projects["flutter"])
    rust = await repo.get_node("Project", projects["rust_plan"])
    rows.append(
        _check(
            "UC-01 status preserved",
            (flutter or {}).get("status") == "in_progress"
            and (rust or {}).get("status") == "planned",
            f"flutter={flutter and flutter.get('status')} rust={rust and rust.get('status')}",
        )
    )

    skills = await repo.get_person_skills(person)
    held = {
        resolve_canonical_skill_name(str(s.get("name") or ""))
        for s in skills
        if s.get("name")
    }
    leaked = held & MUST_NOT_HAS_SKILL
    rows.append(
        _check(
            "UC-01 HAS_SKILL only finished",
            not leaked,
            f"forbidden skills on person: {sorted(leaked)}",
        )
    )

    python = next(
        (s for s in skills if resolve_canonical_skill_name(str(s.get("name"))) == "Python"),
        {},
    )
    rows.append(
        _check(
            "UC-01 skill level monotonic",
            str(python.get("level")) == "expert",
            f"Python level={python.get('level')} (tutorial was beginner)",
        )
    )

    react_ids = await repo.query(
        "MATCH (s:Skill) WHERE s.name = 'React' RETURN s.id AS id, s.aliases AS aliases"
    )
    rows.append(
        _check(
            "UC-01 alias collapse React.js",
            len(react_ids) == 1,
            f"React skill nodes={len(react_ids)}",
        )
    )

    dual = await repo.query(
        "MATCH (j:JobOffer) RETURN count(j) AS c"
    )
    rows.append(
        _check(
            "UC-02 jobs in graph",
            int(dual[0]["c"]) >= 18,
            f"JobOffer count={dual[0]['c']}",
        )
    )
    requires = await repo.query(
        "MATCH (:JobOffer)-[:REQUIRES]->(:Skill) RETURN count(*) AS c"
    )
    rows.append(
        _check(
            "UC-02 REQUIRES edges",
            int(requires[0]["c"]) > 0,
            f"REQUIRES count={requires[0]['c']}",
        )
    )

    apps = await repo.query(
        "MATCH (:Person {id: $pid})-[:APPLIED_TO]->(a:Application)"
        "-[:FOR_OFFER]->(:JobOffer) RETURN count(a) AS c",
        {"pid": person},
    )
    rows.append(
        _check(
            "UC-02/UC-05 applications linked",
            int(apps[0]["c"]) >= 3,
            f"applications={apps[0]['c']}",
        )
    )

    emp = await repo.query(
        "MATCH (:Person {id: $pid})-[:WORKED_AT]->(e:Employment) RETURN count(e) AS c",
        {"pid": person},
    )
    edu = await repo.query(
        "MATCH (:Person {id: $pid})-[:STUDIED_AT]->(e:Education) RETURN count(e) AS c",
        {"pid": person},
    )
    cert = await repo.query(
        "MATCH (:Person {id: $pid})-[:HAS_CERTIFICATE]->(c:Certificate) RETURN count(c) AS c",
        {"pid": person},
    )
    rows.append(
        _check(
            "UC-03/UC-07 chronology",
            int(emp[0]["c"]) >= 1 and int(edu[0]["c"]) >= 1 and int(cert[0]["c"]) >= 1,
            f"employment={emp[0]['c']} education={edu[0]['c']} certs={cert[0]['c']}",
        )
    )

    b_proj = projects.get("person_b")
    leak = await repo.query(
        "MATCH (p:Person {id: $pid})-[:PRODUCED]->(pr:Project {id: $proj}) "
        "RETURN count(pr) AS c",
        {"pid": person, "proj": b_proj},
    )
    rows.append(
        _check(
            "UC-06 person scope",
            int(leak[0]["c"]) == 0 and bool(b_proj),
            "person A does not PRODUCE person B's project",
        )
    )
    b_node = await repo.get_node("Person", PERSON_B)
    rows.append(
        _check("UC-06 person B exists", bool(b_node), f"person B id={PERSON_B}")
    )

    # Live ingest of one extra finished project (UC-01 write path).
    ingestion = KGIngestion(
        kg_repository=repo, embeddings=KGEmbeddings(kg_repository=repo)
    )
    extra_id = await ingestion.ingest_project(
        title="Eval Extra CLI",
        description="Tiny finished CLI in Python.",
        tech_stack=["Python"],
        metadata={"status": "finished", "source": "form", "start_date": "2026-01-01"},
        person_id=person,
        skills=[
            {
                "name": "Python",
                "canonical_name": "Python",
                "category": "technical",
                "level": "beginner",
                "confidence": 1.0,
            }
        ],
    )
    await repo.upsert_relationship("Person", person, "PRODUCED", "Project", extra_id)
    await repo.ensure_has_skill_for_finished_projects(person, extra_id)
    python_after = await repo.get_node("Skill", "skill_python")
    extra = await repo.get_node("Project", extra_id)
    rows.append(
        _check(
            "UC-01 ingest extra project",
            bool(extra) and (python_after or {}).get("level") == "expert",
            f"extra={extra_id} python_level={python_after and python_after.get('level')}",
        )
    )
    await repo.query("MATCH (n {id: $id}) DETACH DELETE n", {"id": extra_id})

    passed = sum(1 for row in rows if row["pass"])
    return {
        "n": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "task_completion_rate": passed / len(rows) if rows else 0.0,
        "rows": rows,
        "jobs_seeded": jobs,
    }
