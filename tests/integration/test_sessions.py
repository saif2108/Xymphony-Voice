from uuid import uuid4

from fastapi.testclient import TestClient

from tests.integration.conftest import BINDING


def _create_agent_with_published_version(client: TestClient, project_id: str) -> tuple[str, str]:
    created = client.post(
        f"/v1/projects/{project_id}/agents",
        json={"name": "Voice Agent"},
    )
    assert created.status_code == 201
    agent_id = created.json()["id"]
    version = client.post(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions",
        json={"instructions": "You are helpful.", **BINDING},
    )
    assert version.status_code == 201
    version_id = version.json()["id"]
    published = client.post(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}/publish",
    )
    assert published.status_code == 200
    return agent_id, version_id


def test_create_and_get_session(client: TestClient, project_id: str) -> None:
    agent_id, version_id = _create_agent_with_published_version(client, project_id)
    created = client.post(
        f"/v1/projects/{project_id}/sessions",
        json={"agent_id": agent_id},
    )
    assert created.status_code == 201
    session = created.json()
    assert session["agent_id"] == agent_id
    assert session["agent_version_id"] == version_id
    assert session["project_id"] == project_id
    assert session["status"] == "initializing"

    fetched = client.get(f"/v1/projects/{project_id}/sessions/{session['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == session["id"]
    assert fetched.json()["agent_version_id"] == version_id


def test_session_pins_explicit_agent_version(client: TestClient, project_id: str) -> None:
    agent_id, published_version_id = _create_agent_with_published_version(client, project_id)
    draft = client.post(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions",
        json={"instructions": "Draft version.", **BINDING},
    )
    draft_version_id = draft.json()["id"]
    created = client.post(
        f"/v1/projects/{project_id}/sessions",
        json={"agent_id": agent_id, "agent_version_id": draft_version_id},
    )
    assert created.status_code == 201
    assert created.json()["agent_version_id"] == draft_version_id
    assert created.json()["agent_version_id"] != published_version_id


def test_create_session_requires_published_version(client: TestClient, project_id: str) -> None:
    created = client.post(
        f"/v1/projects/{project_id}/agents",
        json={"name": "No Version Agent"},
    )
    agent_id = created.json()["id"]
    response = client.post(
        f"/v1/projects/{project_id}/sessions",
        json={"agent_id": agent_id},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "no_published_version"


def test_list_session_messages_empty(client: TestClient, project_id: str) -> None:
    agent_id, _version_id = _create_agent_with_published_version(client, project_id)
    created = client.post(
        f"/v1/projects/{project_id}/sessions",
        json={"agent_id": agent_id},
    )
    session_id = created.json()["id"]
    listed = client.get(f"/v1/projects/{project_id}/sessions/{session_id}/messages")
    assert listed.status_code == 200
    assert listed.json()["items"] == []


def test_session_not_found(client: TestClient, project_id: str) -> None:
    response = client.get(f"/v1/projects/{project_id}/sessions/{uuid4()}")
    assert response.status_code == 404
