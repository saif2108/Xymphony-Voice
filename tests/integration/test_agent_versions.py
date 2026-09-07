from fastapi.testclient import TestClient

from tests.integration.conftest import BINDING


def _create_agent(client: TestClient, project_id: str) -> str:
    response = client.post(f"/v1/projects/{project_id}/agents", json={"name": "Configured"})
    assert response.status_code == 201
    return str(response.json()["id"])


def test_create_and_get_version(client: TestClient, project_id: str) -> None:
    agent_id = _create_agent(client, project_id)
    created = client.post(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions",
        json={
            "instructions": "Be helpful.",
            "personality": "calm",
            **BINDING,
        },
    )
    assert created.status_code == 201
    version = created.json()
    assert version["agent_id"] == agent_id
    assert version["version_n"] == 1
    assert version["status"] == "draft"
    assert version["config_hash"]
    assert version["llm"]["provider_key"] == "openai_compatible"
    assert "api_key" not in version["llm"]

    fetched = client.get(f"/v1/projects/{project_id}/agents/{agent_id}/versions/{version['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["instructions"] == "Be helpful."

    listed = client.get(f"/v1/projects/{project_id}/agents/{agent_id}/versions")
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1


def test_patch_draft_version(client: TestClient, project_id: str) -> None:
    agent_id = _create_agent(client, project_id)
    created = client.post(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions",
        json={"instructions": "One", **BINDING},
    )
    version_id = created.json()["id"]
    original_hash = created.json()["config_hash"]
    patched = client.patch(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}",
        json={"instructions": "Two"},
    )
    assert patched.status_code == 200
    assert patched.json()["instructions"] == "Two"
    assert patched.json()["config_hash"] != original_hash
    assert patched.json()["version_n"] == 1


def test_secret_params_rejected(client: TestClient, project_id: str) -> None:
    agent_id = _create_agent(client, project_id)
    payload = {
        "instructions": "Hi",
        "llm": {"provider_key": "openai_compatible", "model": "x", "params": {"api_key": "sk"}},
        "stt": BINDING["stt"],
        "tts": BINDING["tts"],
    }
    response = client.post(f"/v1/projects/{project_id}/agents/{agent_id}/versions", json=payload)
    assert response.status_code == 422


def test_published_version_cannot_be_patched(client: TestClient, project_id: str) -> None:
    agent_id = _create_agent(client, project_id)
    created = client.post(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions",
        json={"instructions": "Live", **BINDING},
    )
    version_id = created.json()["id"]
    published = client.post(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}/publish"
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["published_at"] is not None

    patched = client.patch(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}",
        json={"instructions": "Mutated"},
    )
    assert patched.status_code == 409
    assert patched.json()["code"] == "conflict_published_immutable"

    fetched = client.get(f"/v1/projects/{project_id}/agents/{agent_id}/versions/{version_id}")
    assert fetched.json()["instructions"] == "Live"


def test_second_version_increments(client: TestClient, project_id: str) -> None:
    agent_id = _create_agent(client, project_id)
    first = client.post(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions",
        json={"instructions": "v1", **BINDING},
    )
    second = client.post(
        f"/v1/projects/{project_id}/agents/{agent_id}/versions",
        json={"instructions": "v2", **BINDING},
    )
    assert first.json()["version_n"] == 1
    assert second.json()["version_n"] == 2
