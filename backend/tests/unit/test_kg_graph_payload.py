from app.api.v1.kg import _attach_skill_metrics


def test_attach_skill_metrics_counts_demand_evidence_and_direct_links() -> None:
    nodes = [
        {
            "id": "skill_1",
            "type": "Skill",
            "data": {"label": "Python", "properties": {"name": "Python"}},
        },
        {
            "id": "project_1",
            "type": "Project",
            "data": {"label": "App", "properties": {}},
        },
    ]
    edges = [
        {"id": "e1", "source": "user_1", "target": "skill_1", "label": "HAS_SKILL"},
        {"id": "e2", "source": "project_1", "target": "skill_1", "label": "USES"},
        {"id": "e3", "source": "job_1", "target": "skill_1", "label": "REQUIRES"},
        {"id": "e4", "source": "job_2", "target": "skill_1", "label": "REQUIRES"},
    ]

    _attach_skill_metrics(nodes, edges)

    props = nodes[0]["data"]["properties"]
    assert props["demand_count"] == 2
    assert props["evidence_count"] == 1
    assert props["has_direct_link"] is True
    assert "demand_count" not in nodes[1]["data"]["properties"]


def test_attach_skill_metrics_uses_owned_skill_ids_when_provided() -> None:
    nodes = [
        {
            "id": "skill_finished_only",
            "type": "Skill",
            "data": {"label": "Docker", "properties": {"name": "Docker"}},
        },
    ]
    edges = [
        {
            "id": "e1",
            "source": "project_1",
            "target": "skill_finished_only",
            "label": "USES",
        },
    ]

    _attach_skill_metrics(nodes, edges, owned_skill_ids={"skill_finished_only"})

    assert nodes[0]["data"]["properties"]["has_direct_link"] is True
