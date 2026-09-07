"""LiveKit rtc.Room adapter implementing MediaTransport. Not LiveKit Agents."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from typing import cast

from livekit import rtc

from xymphony_contracts.media_transport import (
    ConnectionStateHandler,
    MediaTransportConfig,
    ParticipantEventHandler,
    TransportConnectionState,
    TransportErrorEvent,
    TransportErrorHandler,
    TransportParticipantEvent,
    TransportParticipantEventKind,
)

logger = logging.getLogger(__name__)


class LiveKitMediaTransport:
    """MediaTransport backed by livekit.rtc.Room."""

    def __init__(self) -> None:
        self._room = rtc.Room()
        self._state = TransportConnectionState.DISCONNECTED
        self._config: MediaTransportConfig | None = None
        self._participant_handlers: list[ParticipantEventHandler] = []
        self._state_handlers: list[ConnectionStateHandler] = []
        self._error_handlers: list[TransportErrorHandler] = []
        self._disconnect_event = asyncio.Event()
        self._handlers_registered = False

    @property
    def connection_state(self) -> TransportConnectionState:
        return self._state

    @property
    def room(self) -> rtc.Room:
        return self._room

    def on_participant_event(self, handler: ParticipantEventHandler) -> None:
        self._participant_handlers.append(handler)

    def on_connection_state(self, handler: ConnectionStateHandler) -> None:
        self._state_handlers.append(handler)

    def on_error(self, handler: TransportErrorHandler) -> None:
        self._error_handlers.append(handler)

    async def connect(self, config: MediaTransportConfig) -> None:
        self._config = config
        self._register_room_handlers()
        await self._set_state(TransportConnectionState.CONNECTING)
        try:
            await self._room.connect(config.url, config.token)
        except Exception as exc:
            await self._emit_error("connect_failed", str(exc), retryable=True)
            await self._set_state(TransportConnectionState.FAILED)
            raise
        await self._set_state(TransportConnectionState.CONNECTED)
        logger.info(
            "livekit_connected",
            extra={"room": config.room_name, "identity": config.participant_identity},
        )

    async def disconnect(self) -> None:
        if self._state == TransportConnectionState.DISCONNECTED:
            return
        try:
            await self._room.disconnect()
        finally:
            await self._set_state(TransportConnectionState.DISCONNECTED)
            self._disconnect_event.set()
            logger.info("livekit_disconnected")

    async def wait_until_disconnected(self) -> None:
        await self._disconnect_event.wait()

    def _register_room_handlers(self) -> None:
        if self._handlers_registered:
            return
        self._handlers_registered = True

        def current_room_name() -> str:
            return self._config.room_name if self._config else ""

        @self._room.on("participant_connected")
        def _on_participant_connected(participant: rtc.RemoteParticipant) -> None:
            asyncio.create_task(
                self._emit_participant(
                    TransportParticipantEvent(
                        kind=TransportParticipantEventKind.CONNECTED,
                        identity=participant.identity,
                        room_name=current_room_name(),
                    )
                )
            )

        @self._room.on("participant_disconnected")
        def _on_participant_disconnected(participant: rtc.RemoteParticipant) -> None:
            asyncio.create_task(
                self._emit_participant(
                    TransportParticipantEvent(
                        kind=TransportParticipantEventKind.LEFT,
                        identity=participant.identity,
                        room_name=current_room_name(),
                    )
                )
            )

        @self._room.on("disconnected")
        def _on_disconnected(_reason: rtc.DisconnectReason) -> None:
            asyncio.create_task(self._handle_room_disconnected())

        @self._room.on("connection_state_changed")
        def _on_connection_state_changed(state: rtc.ConnectionState) -> None:
            mapped = _map_connection_state(cast(int, state))
            asyncio.create_task(self._set_state(mapped))

    async def _handle_room_disconnected(self) -> None:
        await self._set_state(TransportConnectionState.DISCONNECTED)
        self._disconnect_event.set()

    async def _set_state(self, state: TransportConnectionState) -> None:
        self._state = state
        for handler in self._state_handlers:
            await _maybe_await(handler(state))

    async def _emit_participant(self, event: TransportParticipantEvent) -> None:
        for handler in self._participant_handlers:
            await _maybe_await(handler(event))

    async def _emit_error(self, code: str, message: str, *, retryable: bool) -> None:
        event = TransportErrorEvent(code=code, message=message, retryable=retryable)
        for handler in self._error_handlers:
            await _maybe_await(handler(event))


def _map_connection_state(state: int) -> TransportConnectionState:
    if state == rtc.ConnectionState.CONN_CONNECTED:
        return TransportConnectionState.CONNECTED
    if state == rtc.ConnectionState.CONN_RECONNECTING:
        return TransportConnectionState.RECONNECTING
    if state == rtc.ConnectionState.CONN_DISCONNECTED:
        return TransportConnectionState.DISCONNECTED
    return TransportConnectionState.CONNECTING


async def _maybe_await(result: Awaitable[None] | None) -> None:
    if result is not None:
        await result
