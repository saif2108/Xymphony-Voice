"""RuntimeWorkerSession orchestration tests."""

import asyncio

import pytest

from xymphony_contracts.media_transport import MediaTransportConfig
from xymphony_realtime import FakeMediaTransport
from xymphony_runtime import RuntimeSessionLifecycleState, RuntimeWorkerSession


@pytest.mark.asyncio
async def test_worker_session_runs_lifecycle() -> None:
    transport = FakeMediaTransport()
    worker = RuntimeWorkerSession(session_id="worker-1")
    config = MediaTransportConfig(
        url="wss://example.livekit.cloud",
        room_name="dev-room",
        participant_identity="worker",
        token="token",
    )

    run_task = asyncio.create_task(worker.run(transport, config))
    await asyncio.sleep(0)
    await worker.shutdown()
    await run_task

    assert worker.lifecycle_state == RuntimeSessionLifecycleState.STOPPED
    assert transport.connect_calls == 1
    assert transport.disconnect_calls == 1
