from app.pipelines.skill_analysis_pipeline import normalize_skill_analysis


def test_normalize_includes_suggested_projects() -> None:
    """normalize_skill_analysis only shapes suggested_projects now - gaps
    and core strengths are computed deterministically in Python (see
    build_gap_analysis_result), not by the LLM."""
    result = normalize_skill_analysis(
        {
            "suggested_projects": [
                {
                    "title": "Career Graph Assistant",
                    "description": "Build an end-to-end GraphRAG app",
                    "tech_stack": ["Neo4j", "FastAPI"],
                    "skills_covered": ["Neo4j", "GraphRAG", "FastAPI"],
                }
            ],
        }
    )
    assert len(result["suggested_projects"]) == 1
    assert result["suggested_projects"][0]["title"] == "Career Graph Assistant"
    assert "Neo4j" in result["suggested_projects"][0]["skills_covered"]
