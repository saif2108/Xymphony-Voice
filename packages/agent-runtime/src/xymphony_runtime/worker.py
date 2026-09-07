"""Runtime worker session orchestration for the worker process."""

from __future__ import annotations

import asyncio
import logging
import signal

from xymphony_contracts.media_transport import MediaTransportConfig
from xymphony_runtime.bridge import RuntimeMediaBridge
from xymphony_runtime.lifecycle import RuntimeSessionLifecycleState
from xymphony_runtime.observations import RuntimeObservation

logger = logging.getLogger(__name__)


class RuntimeWorkerSession:
    """Owns RuntimeMediaBridge lifecycle inside the runtime worker process."""

    def __init__(self, bridge: RuntimeMediaBridge) -> None:
        self._bridge = bridge

    @property
    def session_id(self) -> str:
        return str(self._bridge.runtime.context.session_id)

    @property
    def bridge(self) -> RuntimeMediaBridge:
        return self._bridge

    @property
    def lifecycle_state(self) -> RuntimeSessionLifecycleState:
        return self._bridge.lifecycle_state

    @property
    def observations(self) -> tuple[RuntimeObservation, ...]:
        return self._bridge.observations

    async def run(self, config: MediaTransportConfig) -> None:
        self._install_signal_handlers()
        logger.info(
            "worker_session_starting",
            extra={"session_id": self.session_id, "room": config.room_name},
        )
        await self._bridge.run(config)
        logger.info(
            "worker_session_ended",
            extra={
                "session_id": self.session_id,
                "lifecycle_state": self.lifecycle_state.value,
            },
        )

    async def shutdown(self) -> None:
        logger.info("worker_session_shutdown_requested", extra={"session_id": self.session_id})
        await self._bridge.shutdown()

    def _install_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()

        def _request_shutdown() -> None:
            asyncio.create_task(self.shutdown())

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _request_shutdown)
            except NotImplementedError:
                pass
