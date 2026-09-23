from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.integration.conftest import BINDING
from xymphony_api.models import AgentVersionKnowledgeBaseRow, DocumentChunkRow
from xymphony_api.repositories import DocumentChunkRepository
from xymphony_rag.embeddings import LocalEmbeddingProvider


def _create_knowledge_base(client: TestClient, project_id: str) -> dict:
    response = client.post(
        f"/v1/projects/{project_id}/knowledge-bases",
        json={
            "name": "Test Knowledge Base",
            "description": "Knowledge base for integration testing.",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_and_list_knowledge_base(
    client: TestClient,
    project_id: str,
) -> None:
    knowledge_base = _create_knowledge_base(client, project_id)

    assert knowledge_base["name"] == "Test Knowledge Base"
    assert knowledge_base["description"] == "Knowledge base for integration testing."
    assert knowledge_base["project_id"] == project_id

    response = client.get(
        f"/v1/projects/{project_id}/knowledge-bases",
    )

    assert response.status_code == 200

    items = response.json()["items"]
    assert any(item["id"] == knowledge_base["id"] for item in items)


def test_create_and_list_documents(
    client: TestClient,
    project_id: str,
    db_session,
) -> None:
    knowledge_base = _create_knowledge_base(client, project_id)
    knowledge_base_id = knowledge_base["id"]

    response = client.post(
        f"/v1/knowledge-bases/{knowledge_base_id}/documents",
        json={
            "name": "Test Document",
            "content": (
                "Xymphony Voice is a platform for building intelligent realtime voice agents."
            ),
        },
    )

    assert response.status_code == 201

    document = response.json()
    assert document["name"] == "Test Document"
    assert "id" in document
    assert "created_at" in document

    chunks = (
        db_session.execute(
            select(DocumentChunkRow).where(
                DocumentChunkRow.document_id == document["id"],
            )
        )
        .scalars()
        .all()
    )

    assert len(chunks) > 0
    assert chunks[0].content
    assert chunks[0].embedding is not None
    assert len(chunks[0].embedding) == 384
    assert chunks[0].search_vector is not None

    response = client.get(
        f"/v1/knowledge-bases/{knowledge_base_id}/documents",
    )

    assert response.status_code == 200

    items = response.json()["items"]

    assert any(item["id"] == document["id"] for item in items)

def test_hybrid_retrieval_returns_relevant_chunk(
    client: TestClient,
    project_id: str,
    db_session,
) -> None:
    knowledge_base = _create_knowledge_base(client, project_id)
    knowledge_base_id = knowledge_base["id"]

    agent = client.post(
        f"/v1/projects/{project_id}/agents",
        json={"name": "RAG Test Agent"},
    )
    assert agent.status_code == 201
    agent_id = agent.json()["id"]

    version = client.post(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions",
        json={"instructions": "You are helpful.", **BINDING},
    )
    assert version.status_code == 201
    version_id = UUID(version.json()["id"])

    db_session.add(
        AgentVersionKnowledgeBaseRow(
            agent_version_id=version_id,
            knowledge_base_id=UUID(knowledge_base_id),
        )
    )
    db_session.flush()

    document = client.post(
        f"/v1/knowledge-bases/{knowledge_base_id}/documents",
        json={
            "name": "Product Information",
            "content": (
                "Xymphony Voice provides realtime AI voice agents. "
                "Agents can use knowledge bases to answer questions."
            ),
        },
    )
    assert document.status_code == 201

    embedding_provider = LocalEmbeddingProvider()
    query_embedding = embedding_provider.embed(
        "How do I build a realtime voice agent?"
    )

    repository = DocumentChunkRepository(db_session)
    results = repository.search_hybrid(
        agent_version_id=version_id,
        query="How do I build a realtime voice agent?",
        query_embedding=query_embedding,
        limit=5,
    )

    assert results
    assert "realtime AI voice agents" in results[0].content