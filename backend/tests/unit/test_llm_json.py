from __future__ import annotations

import pytest

from app.utils.llm_json import extract_json_from_llm_output


def test_extract_json_from_markdown_with_comments() -> None:
    raw = """```json
{
  "core_strengths": [
    "Python",
    "AWS"
  ],
  "skill_gaps": [
    "neo4j"  // not in market demand
  ],
  "learning_plan": [
    {
      "step": "Improve neo4j skills",
      "priority": "High"
    }
  ]
}
```

Note: subjective priorities.
"""
    result = extract_json_from_llm_output(raw)

    assert result["core_strengths"] == ["Python", "AWS"]
    assert result["skill_gaps"] == ["neo4j"]
    assert result["learning_plan"][0]["step"] == "Improve neo4j skills"


def test_extract_json_with_control_characters_in_strings() -> None:
    raw = """{
  "core_strengths": ["Python"],
  "skill_gaps": [
    {
      "skill": "Docker",
      "gap_reason": "Required for deployment
and container orchestration",
      "priority": "high"
    }
  ],
  "learning_plan": [],
  "estimated_time": "2 weeks"
}"""
    result = extract_json_from_llm_output(raw)

    assert result["core_strengths"] == ["Python"]
    assert "deployment" in result["skill_gaps"][0]["gap_reason"]
    assert "container orchestration" in result["skill_gaps"][0]["gap_reason"]


def test_extract_json_with_trailing_commas() -> None:
    raw = """{
  "core_strengths": ["Python",],
  "skill_gaps": [
    {
      "skill": "Docker",
      "gap_reason": "Needed for deployment",
      "priority": "high",
    },
  ],
  "learning_plan": [],
  "estimated_time": "2 weeks",
}"""
    result = extract_json_from_llm_output(raw)

    assert result["core_strengths"] == ["Python"]
    assert result["skill_gaps"][0]["skill"] == "Docker"


def test_extract_json_rejects_non_object() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        extract_json_from_llm_output("[1, 2, 3]")
