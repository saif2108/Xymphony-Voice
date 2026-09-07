"""Minimal transport-only runtime session (Step 3/4). No LLM/STT/TTS."""

from __future__ import annotations

import asyncio
import logging

from xymphony_contracts.media_transport import (
    MediaTransport,
    MediaTransportConfig,
    TransportConnectionState,
    TransportErrorEvent,
    TransportParticipantEvent,
)
from xymphony_runtime.lifecycle import RuntimeSessionLifecycleState
from xymphony_runtime.observations import RuntimeObservation, lifecycle_transition

logger = logging.getLogger(__name__)


class MinimalTransportSession:
    """Runs a session lifecycle over MediaTransport without provider adapters."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._shutdown = asyncio.Event()
        self._lifecycle_state = RuntimeSessionLifecycleState.INITIALIZING
        self._observations: list[RuntimeObservation] = []
        self._background_tasks: set[asyncio.Task[None]] = set()
        self.connection_states: list[TransportConnectionState] = []
        self.participant_events: list[TransportParticipantEvent] = []
        self.errors: list[TransportErrorEvent] = []

    @property
    def lifecycle_state(self) -> RuntimeSessionLifecycleState:
        return self._lifecycle_state

    @property
    def observations(self) -> tuple[RuntimeObservation, ...]:
        return tuple(self._observations)

    async def run(self, transport: MediaTransport, config: MediaTransportConfig) -> None:
        self._transition(RuntimeSessionLifecycleState.INITIALIZING)
        transport.on_connection_state(self._on_connection_state)
        transport.on_participant_event(self._on_participant_event)
        transport.on_error(self._on_error)

        logger.info(
            "session_starting",
            extra={"session_id": self.session_id, "room": config.room_name},
        )
        wait_tasks: list[asyncio.Task[None]] = []
        try:
            self._transition(RuntimeSessionLifecycleState.CONNECTING)
            await transport.connect(config)
            self._transition(RuntimeSessionLifecycleState.CONNECTED)

            disconnect_task = self._track_task(
                asyncio.create_task(
                    transport.wait_until_disconnected(),
                    name=f"session-{self.session_id}-wait-disconnect",
                )
            )
            shutdown_task = self._track_task(
                asyncio.create_task(
                    self._wait_for_shutdown(),
                    name=f"session-{self.session_id}-wait-shutdown",
                )
            )
            wait_tasks = [disconnect_task, shutdown_task]

            done, pending = await asyncio.wait(wait_tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
            await self._cancel_tasks(pending)
        except asyncio.CancelledError:
            self._transition(RuntimeSessionLifecycleState.STOPPING)
            raise
        except Exception as exc:
            self._record_error(
                TransportErrorEvent(
                    code="session_connect_failed",
                    message=str(exc),
                    retryable=False,
                )
            )
            self._transition(RuntimeSessionLifecycleState.FAILED)
            logger.exception(
                "session_connect_failed",
                extra={"session_id": self.session_id},
            )
        else:
            if self._shutdown.is_set():
                self._transition(RuntimeSessionLifecycleState.STOPPING)
        finally:
            await self._cancel_tasks(wait_tasks)
            if self._lifecycle_state not in {
                RuntimeSessionLifecycleState.FAILED,
                RuntimeSessionLifecycleState.STOPPING,
            }:
                self._transition(RuntimeSessionLifecycleState.STOPPING)
            try:
                await transport.disconnect()
            finally:
                if self._lifecycle_state == RuntimeSessionLifecycleState.FAILED:
                    pass
                else:
                    self._transition(RuntimeSessionLifecycleState.STOPPED)
                logger.info("session_ended", extra={"session_id": self.session_id})

    async def shutdown(self) -> None:
        self._shutdown.set()

    async def _wait_for_shutdown(self) -> None:
        await self._shutdown.wait()

    async def _on_connection_state(self, state: TransportConnectionState) -> None:
        self.connection_states.append(state)
        logger.info(
            "transport_state",
            extra={"session_id": self.session_id, "state": state.value},
        )

    async def _on_participant_event(self, event: TransportParticipantEvent) -> None:
        self.participant_events.append(event)
        self._observations.append(event)
        logger.info(
            "participant_event",
            extra={
                "session_id": self.session_id,
                "kind": event.kind.value,
                "identity": event.identity,
            },
        )

    async def _on_error(self, event: TransportErrorEvent) -> None:
        self._record_error(event)

    def _record_error(self, event: TransportErrorEvent) -> None:
        self.errors.append(event)
        self._observations.append(event)
        logger.error(
            "transport_error",
            extra={
                "session_id": self.session_id,
                "code": event.code,
                "error_message": event.message,
            },
        )

    def _transition(self, state: RuntimeSessionLifecycleState) -> None:
        self._lifecycle_state = state
        transition = lifecycle_transition(state)
        self._observations.append(transition)
        logger.info(
            "lifecycle_state",
            extra={"session_id": self.session_id, "state": state.value},
        )

    def _track_task(self, task: asyncio.Task[None]) -> asyncio.Task[None]:
        self._background_tasks.add(task)

        def _done(completed: asyncio.Task[None]) -> None:
            self._background_tasks.discard(completed)

        task.add_done_callback(_done)
        return task

    async def _cancel_tasks(
        self,
        tasks: set[asyncio.Task[None]] | list[asyncio.Task[None]],
    ) -> None:
        for task in tasks:
            if task.done():
                continue
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
