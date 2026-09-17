from fastapi.testclient import TestClient
from sqlalchemy import select

from xymphony_api.models import DocumentChunkRow


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

    response = client.get(
        f"/v1/knowledge-bases/{knowledge_base_id}/documents",
    )

    assert response.status_code == 200

    items = response.json()["items"]

    assert any(item["id"] == document["id"] for item in items)
