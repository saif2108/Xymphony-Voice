from uuid import uuid4

from fastapi.testclient import TestClient

from tests.integration.conftest import BINDING


def _create_agent(client: TestClient, project_id: str) -> str:
    response = client.post(f"/v1/projects/{project_id}/agents", json={"name": "Configured"})
    assert response.status_code == 201
    return str(response.json()["id"])


def _create_draft_version(client: TestClient, project_id: str, agent_id: str) -> str:
    response = client.post(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions",
        json={"instructions": "Be helpful.", **BINDING},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def _create_tool(client: TestClient, project_id: str, name: str = "get_weather") -> dict:
    response = client.post(
        f"/v1/projects/{project_id}/tools",
        json={
            "name": name,
            "description": "Looks up current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_list_get_update_delete_tool(client: TestClient, project_id: str) -> None:
    tool = _create_tool(client, project_id)
    assert tool["name"] == "get_weather"
    assert tool["tool_type"] == "function"
    assert tool["enabled"] is True
    assert tool["project_id"] == project_id
    assert tool["organization_id"]
    tool_id = tool["id"]

    listed = client.get(f"/v1/projects/{project_id}/tools")
    assert listed.status_code == 200
    ids = [item["id"] for item in listed.json()["items"]]
    assert tool_id in ids

    fetched = client.get(f"/v1/projects/{project_id}/tools/{tool_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == tool_id

    patched = client.patch(
        f"/v1/projects/{project_id}/tools/{tool_id}",
        json={"description": "Updated description.", "enabled": False},
    )
    assert patched.status_code == 200
    assert patched.json()["description"] == "Updated description."
    assert patched.json()["enabled"] is False

    persisted = client.get(f"/v1/projects/{project_id}/tools/{tool_id}")
    assert persisted.json()["enabled"] is False

    deleted = client.delete(f"/v1/projects/{project_id}/tools/{tool_id}")
    assert deleted.status_code == 204
    missing = client.get(f"/v1/projects/{project_id}/tools/{tool_id}")
    assert missing.status_code == 404
    assert missing.json()["code"] == "not_found"


def test_duplicate_tool_name_in_project_rejected(client: TestClient, project_id: str) -> None:
    _create_tool(client, project_id, name="dupe")
    response = client.post(f"/v1/projects/{project_id}/tools", json={"name": "dupe"})
    assert response.status_code == 409
    assert response.json()["code"] == "tool_name_exists"


def test_invalid_tool_payload(client: TestClient, project_id: str) -> None:
    response = client.post(f"/v1/projects/{project_id}/tools", json={"name": ""})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_unknown_fields_rejected(client: TestClient, project_id: str) -> None:
    response = client.post(
        f"/v1/projects/{project_id}/tools",
        json={"name": "x", "secret": "nope"},
    )
    assert response.status_code == 422


def test_nonexistent_tool(client: TestClient, project_id: str) -> None:
    response = client.get(f"/v1/projects/{project_id}/tools/{uuid4()}")
    assert response.status_code == 404


def test_nonexistent_project(client: TestClient) -> None:
    response = client.get(f"/v1/projects/{uuid4()}/tools")
    assert response.status_code == 404


def test_tool_not_visible_in_other_project(client: TestClient, project_id: str) -> None:
    tool = _create_tool(client, project_id)
    other = uuid4()
    response = client.get(f"/v1/projects/{other}/tools/{tool['id']}")
    assert response.status_code == 404


def test_attach_detach_and_list_version_tools(client: TestClient, project_id: str) -> None:
    agent_id = _create_agent(client, project_id)
    version_id = _create_draft_version(client, project_id, agent_id)
    tool = _create_tool(client, project_id)
    tool_id = tool["id"]

    attached = client.post(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}/tools/{tool_id}"
    )
    assert attached.status_code == 201
    assert attached.json()["id"] == tool_id

    listed = client.get(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}/tools"
    )
    assert listed.status_code == 200
    ids = [item["id"] for item in listed.json()["items"]]
    assert tool_id in ids

    detached = client.delete(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}/tools/{tool_id}"
    )
    assert detached.status_code == 204

    listed_after = client.get(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}/tools"
    )
    assert listed_after.json()["items"] == []


def test_detach_tool_not_attached_returns_404(client: TestClient, project_id: str) -> None:
    agent_id = _create_agent(client, project_id)
    version_id = _create_draft_version(client, project_id, agent_id)
    tool = _create_tool(client, project_id)

    response = client.delete(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}/tools/{tool['id']}"
    )
    assert response.status_code == 404


def test_attach_nonexistent_tool_returns_404(client: TestClient, project_id: str) -> None:
    agent_id = _create_agent(client, project_id)
    version_id = _create_draft_version(client, project_id, agent_id)

    response = client.post(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}/tools/{uuid4()}"
    )
    assert response.status_code == 404


def test_cannot_attach_tool_to_published_version(client: TestClient, project_id: str) -> None:
    agent_id = _create_agent(client, project_id)
    version_id = _create_draft_version(client, project_id, agent_id)
    tool = _create_tool(client, project_id)

    published = client.post(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}/publish"
    )
    assert published.status_code == 200

    response = client.post(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}/tools/{tool['id']}"
    )
    assert response.status_code == 409
    assert response.json()["code"] == "conflict_published_immutable"


def test_cannot_detach_tool_from_published_version(client: TestClient, project_id: str) -> None:
    agent_id = _create_agent(client, project_id)
    version_id = _create_draft_version(client, project_id, agent_id)
    tool = _create_tool(client, project_id)

    attached = client.post(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}/tools/{tool['id']}"
    )
    assert attached.status_code == 201

    published = client.post(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}/publish"
    )
    assert published.status_code == 200

    response = client.delete(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}/tools/{tool['id']}"
    )
    assert response.status_code == 409
    assert response.json()["code"] == "conflict_published_immutable"