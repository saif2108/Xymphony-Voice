"""Shared helpers for RuntimeMediaBridge integration tests."""

from __future__ import annotations

from tests.helpers import make_session
from tests.unit.runtime.pipeline_helpers import make_pipeline_runtime

from xymphony_contracts.media_transport import MediaTransportConfig
from xymphony_realtime import FakeMediaTransport
from xymphony_runtime import AgentRuntime, RuntimeContext, RuntimeMediaBridge


def bridge_transport_config(*, room_name: str = "dev-room") -> MediaTransportConfig:
    return MediaTransportConfig(
        url="wss://example.livekit.cloud",
        room_name=room_name,
        participant_identity="worker",
        token="token",
    )


def bridge_runtime(**kwargs: object) -> AgentRuntime:
    return make_pipeline_runtime(**kwargs)


def make_bridge(
    *,
    runtime: AgentRuntime | None = None,
    transport: FakeMediaTransport | None = None,
    **runtime_kwargs: object,
) -> RuntimeMediaBridge:
    return RuntimeMediaBridge(
        runtime=runtime or bridge_runtime(**runtime_kwargs),
        transport=transport or FakeMediaTransport(),
    )


def bridge_context() -> RuntimeContext:
    session = make_session()
    assert session.config_hash is not None
    return RuntimeContext(
        session_id=session.id,
        organization_id=session.organization_id,
        project_id=session.project_id,
        agent_id=session.agent_id,
        agent_version_id=session.agent_version_id,
        config_hash=session.config_hash,
    )
