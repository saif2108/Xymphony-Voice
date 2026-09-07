"""Development LiveKit token endpoint — no secrets in response."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from xymphony_api.config import Settings, get_settings
from xymphony_api.main import create_app
from xymphony_realtime import LiveKitParticipantToken


@pytest.fixture
def dev_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("XYMPHONY_ENV", "development")
    monkeypatch.setenv("LIVEKIT_URL", "wss://dev.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test-secret")
    get_settings.cache_clear()
    return TestClient(create_app())


def test_dev_token_mints_participant_jwt(dev_client: TestClient) -> None:
    fake = LiveKitParticipantToken(
        url="wss://dev.livekit.cloud",
        room_name="room-x",
        identity="browser-user",
        token="signed-jwt",
    )
    with patch("xymphony_api.routes.dev_livekit.mint_participant_token", return_value=fake):
        response = dev_client.post(
            "/v1/dev/livekit/token",
            params={"room": "room-x", "identity": "browser-user"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["url"] == "wss://dev.livekit.cloud"
    assert body["room_name"] == "room-x"
    assert body["identity"] == "browser-user"
    assert body["token"] == "signed-jwt"
    assert "secret" not in body


def test_dev_token_hidden_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XYMPHONY_ENV", "production")
    get_settings.cache_clear()
    client = TestClient(create_app())
    response = client.post(
        "/v1/dev/livekit/token",
        params={"room": "room-x", "identity": "browser-user"},
    )
    assert response.status_code == 404


def test_dev_token_requires_livekit_config(dev_client: TestClient) -> None:
    get_settings.cache_clear()
    app = create_app()

    def _settings() -> Settings:
        return Settings(
            xymphony_env="development",
            livekit_url=None,
            livekit_api_key=None,
            livekit_api_secret=None,
        )

    app.dependency_overrides[get_settings] = _settings
    client = TestClient(app)
    response = client.post(
        "/v1/dev/livekit/token",
        params={"room": "room-x", "identity": "browser-user"},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "livekit_not_configured"
