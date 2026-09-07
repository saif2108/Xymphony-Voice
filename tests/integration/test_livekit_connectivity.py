"""Optional LiveKit Cloud connectivity — skipped unless LIVEKIT_INTEGRATION=1."""

from __future__ import annotations

import asyncio
import os

import pytest

from xymphony_contracts.media_transport import MediaTransportConfig
from xymphony_realtime import LiveKitCredentials, LiveKitMediaTransport, mint_participant_token

pytestmark = pytest.mark.livekit


def _integration_enabled() -> bool:
    return os.getenv("LIVEKIT_INTEGRATION") == "1"


@pytest.mark.asyncio
@pytest.mark.skipif(not _integration_enabled(), reason="Set LIVEKIT_INTEGRATION=1 to run")
async def test_livekit_cloud_connect_and_disconnect() -> None:
    url = os.environ["LIVEKIT_URL"]
    api_key = os.environ["LIVEKIT_API_KEY"]
    api_secret = os.environ["LIVEKIT_API_SECRET"]
    room_name = os.getenv("LIVEKIT_ROOM", "xymphony-integration-test")

    participant = mint_participant_token(
        LiveKitCredentials(url=url, api_key=api_key, api_secret=api_secret),
        room_name=room_name,
        identity="integration-worker",
    )
    transport = LiveKitMediaTransport()
    config = MediaTransportConfig(
        url=participant.url,
        room_name=participant.room_name,
        participant_identity=participant.identity,
        token=participant.token,
    )

    await transport.connect(config)
    assert transport.connection_state.value == "connected"
    await transport.disconnect()

    await asyncio.wait_for(transport.wait_until_disconnected(), timeout=5)
