from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.kg.repository import KGRepository


@pytest.mark.asyncio
async def test_upsert_node(
    kg_repository: KGRepository, mock_neo4j_session: AsyncMock
) -> None:
    # Arrange
    label = "Person"
    properties = {"id": "123", "name": "John Doe"}
    mock_record = MagicMock()
    mock_record.__getitem__.return_value = "123"
    mock_result = AsyncMock()
    mock_result.single.return_value = mock_record
    mock_neo4j_session.run.return_value = mock_result

    # Act
    node_id = await kg_repository.upsert_node(label, properties)

    # Assert
    assert node_id == "123"
    mock_neo4j_session.run.assert_called_once()
    args, kwargs = mock_neo4j_session.run.call_args
    assert f"MERGE (node:{label}" in args[0]
    assert kwargs["node_id"] == "123"
    assert kwargs["props"] == properties


@pytest.mark.asyncio
async def test_upsert_relationship(
    kg_repository: KGRepository, mock_neo4j_session: AsyncMock
) -> None:
    # Arrange
    from_label = "Person"
    from_id = "1"
    rel_type = "HAS_SKILL"
    to_label = "Skill"
    to_id = "2"
    properties = {"since": "2021"}
    mock_neo4j_session.run.return_value = AsyncMock()

    # Act
    await kg_repository.upsert_relationship(
        from_label, from_id, rel_type, to_label, to_id, properties
    )

    # Assert
    mock_neo4j_session.run.assert_called_once()
    args, kwargs = mock_neo4j_session.run.call_args
    assert f"MATCH (from:{from_label}" in args[0]
    assert f"MERGE (from)-[rel:{rel_type}]->(to)" in args[0]
    assert kwargs["from_id"] == from_id
    assert kwargs["to_id"] == to_id
    assert kwargs["props"] == properties


@pytest.mark.asyncio
async def test_get_node(
    kg_repository: KGRepository, mock_neo4j_session: AsyncMock
) -> None:
    # Arrange
    label = "Person"
    node_id = "123"
    mock_record = MagicMock()
    mock_record.__getitem__.return_value = {"id": "123", "name": "John Doe"}
    mock_result = AsyncMock()
    mock_result.single.return_value = mock_record
    mock_neo4j_session.run.return_value = mock_result

    # Act
    node = await kg_repository.get_node(label, node_id)

    # Assert
    assert node == {"id": "123", "name": "John Doe"}
    mock_neo4j_session.run.assert_called_once()


@pytest.mark.asyncio
async def test_delete_node(
    kg_repository: KGRepository, mock_neo4j_session: AsyncMock
) -> None:
    # Arrange
    label = "Person"
    node_id = "123"
    mock_neo4j_session.run.return_value = AsyncMock()

    # Act
    await kg_repository.delete_node(label, node_id)

    # Assert
    mock_neo4j_session.run.assert_called_once()
    args, kwargs = mock_neo4j_session.run.call_args
    assert "DETACH DELETE node" in args[0]
    assert kwargs["node_id"] == node_id


@pytest.mark.asyncio
async def test_find_related_nodes(
    kg_repository: KGRepository, mock_neo4j_session: AsyncMock
) -> None:
    # Arrange
    start_label = "Person"
    start_id = "1"
    mock_result = AsyncMock()
    mock_result.data.return_value = [{"node": {"id": "2", "name": "Python"}}]
    mock_neo4j_session.run.return_value = mock_result

    # Act
    related = await kg_repository.find_related_nodes(start_label, start_id)

    # Assert
    assert len(related) == 1
    assert related[0]["id"] == "2"
    mock_neo4j_session.run.assert_called_once()


@pytest.mark.asyncio
async def test_vector_search(
    kg_repository: KGRepository, mock_neo4j_session: AsyncMock
) -> None:
    # Arrange
    label = "Skill"
    embedding = [0.1, 0.2, 0.3]
    mock_result = AsyncMock()
    mock_result.data.return_value = [
        {"node": {"id": "2", "name": "Python"}, "score": 0.9}
    ]
    mock_neo4j_session.run.return_value = mock_result

    # Act
    results = await kg_repository.vector_search(label, embedding)

    # Assert
    assert len(results) == 1
    assert results[0]["node"]["id"] == "2"
    assert results[0]["score"] == 0.9
    mock_neo4j_session.run.assert_called_once()
    args, kwargs = mock_neo4j_session.run.call_args
    assert "CALL db.index.vector.queryNodes" in args[0]
    assert kwargs["embedding"] == embedding


@pytest.mark.asyncio
async def test_get_person_career_brief_returns_categories(
    kg_repository: KGRepository, mock_neo4j_session: AsyncMock
) -> None:
    # Arrange
    person_id = "user_1"
    mock_record = MagicMock()
    mock_record.get.side_effect = lambda key: {
        "projects": [{"title": "Shop API", "skills": ["Python"]}],
        "employment": [{"title": "Backend Engineer", "skills": ["Python", "FastAPI"]}],
        "certificates": [{"title": "CKA", "skills": ["Kubernetes"]}],
        "education": [{"degree": "BSc"}],
    }[key]
    mock_result = AsyncMock()
    mock_result.single.return_value = mock_record
    mock_neo4j_session.run.return_value = mock_result

    # Act
    brief = await kg_repository.get_person_career_brief(person_id)

    # Assert
    assert brief["projects"] == [{"title": "Shop API", "skills": ["Python"]}]
    assert brief["employment"] == [{"title": "Backend Engineer", "skills": ["Python", "FastAPI"]}]
    assert brief["certificates"] == [{"title": "CKA", "skills": ["Kubernetes"]}]
    assert brief["education"] == [{"degree": "BSc"}]
    mock_neo4j_session.run.assert_called_once()
    args, kwargs = mock_neo4j_session.run.call_args
    assert "MATCH (p:Person {id: $person_id})" in args[0]
    assert kwargs["person_id"] == person_id


@pytest.mark.asyncio
async def test_get_person_career_brief_missing_person_returns_empty(
    kg_repository: KGRepository, mock_neo4j_session: AsyncMock
) -> None:
    # Arrange
    mock_result = AsyncMock()
    mock_result.single.return_value = None
    mock_neo4j_session.run.return_value = mock_result

    # Act
    brief = await kg_repository.get_person_career_brief("user_missing")

    # Assert
    assert brief == {"projects": [], "employment": [], "certificates": [], "education": []}


@pytest.mark.asyncio
async def test_query(
    kg_repository: KGRepository, mock_neo4j_session: AsyncMock
) -> None:
    # Arrange
    cypher = "MATCH (n) RETURN n"
    mock_result = AsyncMock()
    mock_result.data.return_value = [{"n": {"id": "1"}}]
    mock_neo4j_session.run.return_value = mock_result

    # Act
    results = await kg_repository.query(cypher)

    # Assert
    assert len(results) == 1
    mock_neo4j_session.run.assert_called_once_with(cypher)


def test_prepare_lucene_query_clips_long_job_descriptions() -> None:
    from app.kg.repository import prepare_lucene_query

    long_text = "Senior Backend Engineer (Ruby). " + ("GitLab platform " * 400)
    prepared = prepare_lucene_query(long_text)
    assert len(prepared.split()) <= 40
    assert "(" not in prepared or "\\(" in prepared
    assert len(prepared) < 500


@pytest.mark.asyncio
async def test_fulltext_search_sends_clipped_query(
    kg_repository: KGRepository, mock_neo4j_session: AsyncMock
) -> None:
    mock_result = AsyncMock()
    mock_result.data = AsyncMock(return_value=[])
    mock_neo4j_session.run.return_value = mock_result

    long_text = "word " * 2000
    await kg_repository.fulltext_search("Skill", long_text, top_k=5)

    sent = mock_neo4j_session.run.call_args.kwargs["query_text"]
    assert len(sent.split()) <= 40
