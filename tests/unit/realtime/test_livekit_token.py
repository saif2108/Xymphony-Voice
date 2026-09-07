"""Token minting uses livekit-api; structure only — no network."""

from unittest.mock import MagicMock, patch

from xymphony_realtime import LiveKitCredentials, mint_participant_token


@patch("xymphony_realtime.livekit_token.api")
def test_mint_participant_token_builds_jwt(mock_api: MagicMock) -> None:
    mock_grant = MagicMock()
    mock_api.VideoGrants.return_value = mock_grant
    token_builder = MagicMock()
    token_builder.with_identity.return_value = token_builder
    token_builder.with_name.return_value = token_builder
    token_builder.with_ttl.return_value = token_builder
    token_builder.with_grants.return_value = token_builder
    token_builder.to_jwt.return_value = "jwt-token"
    mock_api.AccessToken.return_value = token_builder

    result = mint_participant_token(
        LiveKitCredentials(url="wss://lk.example", api_key="key", api_secret="secret"),
        room_name="room-a",
        identity="user-1",
    )

    mock_api.VideoGrants.assert_called_once_with(
        room_join=True,
        room="room-a",
        can_publish=True,
        can_subscribe=True,
    )
    mock_api.AccessToken.assert_called_once_with("key", "secret")
    token_builder.with_identity.assert_called_once_with("user-1")
    assert result.url == "wss://lk.example"
    assert result.room_name == "room-a"
    assert result.identity == "user-1"
    assert result.token == "jwt-token"
