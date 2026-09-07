from uuid import uuid4

from fastapi.testclient import TestClient

from tests.integration.conftest import BINDING


def test_create_list_get_update_delete_agent(client: TestClient, project_id: str) -> None:
    created = client.post(
        f"/v1/projects/{project_id}/agents",
        json={"name": "Support", "description": "Voice agent", "tags": ["p1"]},
    )
    assert created.status_code == 201
    agent = created.json()
    assert agent["name"] == "Support"
    assert agent["description"] == "Voice agent"
    assert agent["project_id"] == project_id
    assert agent["organization_id"]
    agent_id = agent["id"]

    listed = client.get(f"/v1/projects/{project_id}/agents")
    assert listed.status_code == 200
    ids = [item["id"] for item in listed.json()["items"]]
    assert agent_id in ids

    fetched = client.get(f"/v1/projects/{project_id}/agents/{agent_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == agent_id

    patched = client.patch(
        f"/v1/projects/{project_id}/agents/{agent_id}",
        json={"name": "Support Plus", "status": "active"},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Support Plus"
    assert patched.json()["status"] == "active"

    persisted = client.get(f"/v1/projects/{project_id}/agents/{agent_id}")
    assert persisted.json()["name"] == "Support Plus"

    deleted = client.delete(f"/v1/projects/{project_id}/agents/{agent_id}")
    assert deleted.status_code == 204
    missing = client.get(f"/v1/projects/{project_id}/agents/{agent_id}")
    assert missing.status_code == 404
    assert missing.json()["code"] == "not_found"


def test_invalid_agent_payload(client: TestClient, project_id: str) -> None:
    response = client.post(f"/v1/projects/{project_id}/agents", json={"name": ""})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_unknown_fields_rejected(client: TestClient, project_id: str) -> None:
    response = client.post(
        f"/v1/projects/{project_id}/agents",
        json={"name": "X", "secret": "nope"},
    )
    assert response.status_code == 422


def test_nonexistent_agent(client: TestClient, project_id: str) -> None:
    response = client.get(f"/v1/projects/{project_id}/agents/{uuid4()}")
    assert response.status_code == 404


def test_nonexistent_project(client: TestClient) -> None:
    response = client.get(f"/v1/projects/{uuid4()}/agents")
    assert response.status_code == 404


def test_agent_not_visible_in_other_project(client: TestClient, project_id: str) -> None:
    created = client.post(f"/v1/projects/{project_id}/agents", json={"name": "A"})
    agent_id = created.json()["id"]
    other = uuid4()
    response = client.get(f"/v1/projects/{other}/agents/{agent_id}")
    assert response.status_code == 404


def test_create_agent_does_not_need_version_bindings(client: TestClient, project_id: str) -> None:
    """Provider bindings live on AgentVersion, not Agent."""
    response = client.post(f"/v1/projects/{project_id}/agents", json={"name": "Bare", **BINDING})
    assert response.status_code == 422
