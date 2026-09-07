"""Unit tests for FakeMediaTransport lifecycle."""

import pytest

from xymphony_contracts.media_transport import (
    MediaTransportConfig,
    TransportConnectionState,
)
from xymphony_realtime import FakeMediaTransport


@pytest.fixture
def config() -> MediaTransportConfig:
    return MediaTransportConfig(
        url="wss://example.livekit.cloud",
        room_name="test-room",
        participant_identity="worker",
        token="fake-token",
    )


@pytest.mark.asyncio
async def test_fake_transport_connect_and_disconnect(config: MediaTransportConfig) -> None:
    transport = FakeMediaTransport()
    transport.simulate_remote_join_identity = "browser-user"

    states: list[TransportConnectionState] = []
    transport.on_connection_state(lambda s: states.append(s))

    await transport.connect(config)
    assert transport.connection_state == TransportConnectionState.CONNECTED
    assert transport.connect_calls == 1

    await transport.disconnect()
    assert transport.connection_state == TransportConnectionState.DISCONNECTED
    assert transport.disconnect_calls == 1
    assert TransportConnectionState.CONNECTING in states
    assert TransportConnectionState.CONNECTED in states


@pytest.mark.asyncio
async def test_fake_transport_participant_events(config: MediaTransportConfig) -> None:
    transport = FakeMediaTransport()
    transport.simulate_remote_join_identity = "browser-user"
    events: list[str] = []
    transport.on_participant_event(lambda e: events.append(f"{e.kind}:{e.identity}"))

    await transport.connect(config)
    await transport.simulate_remote_leave("browser-user")
    await transport.disconnect()

    assert events == ["connected:browser-user", "left:browser-user"]


@pytest.mark.asyncio
async def test_fake_transport_error_sets_failed(config: MediaTransportConfig) -> None:
    transport = FakeMediaTransport()
    errors: list[str] = []
    transport.on_error(lambda e: errors.append(e.code))

    await transport.connect(config)
    await transport.simulate_error("room_error", "boom")
    assert transport.connection_state == TransportConnectionState.FAILED
    assert errors == ["room_error"]
