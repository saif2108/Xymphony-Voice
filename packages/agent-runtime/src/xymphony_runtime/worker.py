"""Runtime worker session orchestration for the worker process."""

from __future__ import annotations

import asyncio
import logging
import signal

from xymphony_contracts.media_transport import MediaTransport, MediaTransportConfig
from xymphony_runtime.lifecycle import RuntimeSessionLifecycleState
from xymphony_runtime.observations import RuntimeObservation
from xymphony_runtime.session import MinimalTransportSession

logger = logging.getLogger(__name__)


class RuntimeWorkerSession:
    """Owns MinimalTransportSession lifecycle inside the runtime worker process."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._session = MinimalTransportSession(session_id=session_id)

    @property
    def lifecycle_state(self) -> RuntimeSessionLifecycleState:
        return self._session.lifecycle_state

    @property
    def observations(self) -> tuple[RuntimeObservation, ...]:
        return self._session.observations

    @property
    def session(self) -> MinimalTransportSession:
        return self._session

    async def run(self, transport: MediaTransport, config: MediaTransportConfig) -> None:
        self._install_signal_handlers()
        await self._session.run(transport, config)

    async def shutdown(self) -> None:
        await self._session.shutdown()

    def _install_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()

        def _request_shutdown() -> None:
            asyncio.create_task(self.shutdown())

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _request_shutdown)
            except NotImplementedError:
                pass
