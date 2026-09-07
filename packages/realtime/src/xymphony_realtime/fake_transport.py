"""In-memory MediaTransport for unit tests. No network."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable

from xymphony_contracts.media_transport import (
    AudioFrameHandler,
    AudioInputHandler,
    ConnectionStateHandler,
    MediaTransportConfig,
    ParticipantEventHandler,
    TransportAudioFrame,
    TransportAudioInputEvent,
    TransportAudioInputKind,
    TransportAudioOutputFrame,
    TransportConnectionState,
    TransportErrorEvent,
    TransportErrorHandler,
    TransportParticipantEvent,
    TransportParticipantEventKind,
)


class FakeMediaTransport:
    def __init__(self) -> None:
        self._state = TransportConnectionState.DISCONNECTED
        self._config: MediaTransportConfig | None = None
        self._participant_handlers: list[ParticipantEventHandler] = []
        self._state_handlers: list[ConnectionStateHandler] = []
        self._error_handlers: list[TransportErrorHandler] = []
        self._audio_frame_handlers: list[AudioFrameHandler] = []
        self._audio_input_handlers: list[AudioInputHandler] = []
        self._disconnect_event = asyncio.Event()
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.simulate_remote_join_identity: str | None = None
        self.fail_on_connect = False
        self.fail_on_connect_message = "connect failed"
        self.published_output_frames: list[TransportAudioOutputFrame] = []

    @property
    def connection_state(self) -> TransportConnectionState:
        return self._state

    @property
    def config(self) -> MediaTransportConfig | None:
        return self._config

    def on_participant_event(self, handler: ParticipantEventHandler) -> None:
        self._participant_handlers.append(handler)

    def on_connection_state(self, handler: ConnectionStateHandler) -> None:
        self._state_handlers.append(handler)

    def on_error(self, handler: TransportErrorHandler) -> None:
        self._error_handlers.append(handler)

    def on_audio_frame(self, handler: AudioFrameHandler) -> None:
        self._audio_frame_handlers.append(handler)

    def on_audio_input(self, handler: AudioInputHandler) -> None:
        self._audio_input_handlers.append(handler)

    async def connect(self, config: MediaTransportConfig) -> None:
        self.connect_calls += 1
        await self._set_state(TransportConnectionState.CONNECTING)
        if self.fail_on_connect:
            await self._emit_error(
                "connect_failed",
                self.fail_on_connect_message,
                retryable=False,
            )
            await self._set_state(TransportConnectionState.FAILED)
            raise ConnectionError(self.fail_on_connect_message)
        self._config = config
        await self._set_state(TransportConnectionState.CONNECTED)
        if self.simulate_remote_join_identity:
            await self._emit_participant(
                TransportParticipantEvent(
                    kind=TransportParticipantEventKind.CONNECTED,
                    identity=self.simulate_remote_join_identity,
                    room_name=config.room_name,
                )
            )

    async def disconnect(self) -> None:
        if self._state == TransportConnectionState.DISCONNECTED:
            return
        self.disconnect_calls += 1
        await self._set_state(TransportConnectionState.DISCONNECTED)
        self._disconnect_event.set()

    async def wait_until_disconnected(self) -> None:
        await self._disconnect_event.wait()

    async def publish_audio_output(self, frame: TransportAudioOutputFrame) -> None:
        self.published_output_frames.append(frame)

    async def simulate_remote_leave(self, identity: str) -> None:
        if self._config is None:
            return
        await self._emit_participant(
            TransportParticipantEvent(
                kind=TransportParticipantEventKind.LEFT,
                identity=identity,
                room_name=self._config.room_name,
            )
        )

    async def simulate_error(self, code: str, message: str, *, retryable: bool = False) -> None:
        await self._emit_error(code, message, retryable=retryable)
        await self._set_state(TransportConnectionState.FAILED)
        self._disconnect_event.set()

    async def simulate_audio_input_started(self, identity: str) -> None:
        if self._config is None:
            return
        await self._emit_audio_input(
            TransportAudioInputEvent(
                kind=TransportAudioInputKind.STARTED,
                participant_identity=identity,
                room_name=self._config.room_name,
            )
        )

    async def simulate_audio_frame(
        self,
        identity: str,
        data: bytes,
        *,
        duration_ms: int,
        sample_rate_hz: int = 16_000,
        channels: int = 1,
    ) -> None:
        if self._config is None:
            return
        await self._emit_audio_frame(
            TransportAudioFrame(
                participant_identity=identity,
                room_name=self._config.room_name,
                data=data,
                sample_rate_hz=sample_rate_hz,
                channels=channels,
                duration_ms=duration_ms,
            )
        )

    async def simulate_audio_input_ended(self, identity: str) -> None:
        if self._config is None:
            return
        await self._emit_audio_input(
            TransportAudioInputEvent(
                kind=TransportAudioInputKind.ENDED,
                participant_identity=identity,
                room_name=self._config.room_name,
            )
        )

    async def simulate_speech_utterance(
        self,
        identity: str,
        data: bytes,
        *,
        duration_ms: int,
        sample_rate_hz: int = 16_000,
    ) -> None:
        await self.simulate_audio_input_started(identity)
        await self.simulate_audio_frame(
            identity,
            data,
            duration_ms=duration_ms,
            sample_rate_hz=sample_rate_hz,
        )
        await self.simulate_audio_input_ended(identity)

    async def _emit_error(self, code: str, message: str, *, retryable: bool) -> None:
        event = TransportErrorEvent(code=code, message=message, retryable=retryable)
        for handler in self._error_handlers:
            await _maybe_await(handler(event))

    async def _set_state(self, state: TransportConnectionState) -> None:
        self._state = state
        for handler in self._state_handlers:
            await _maybe_await(handler(state))

    async def _emit_participant(self, event: TransportParticipantEvent) -> None:
        for handler in self._participant_handlers:
            await _maybe_await(handler(event))

    async def _emit_audio_frame(self, frame: TransportAudioFrame) -> None:
        for handler in self._audio_frame_handlers:
            await _maybe_await(handler(frame))

    async def _emit_audio_input(self, event: TransportAudioInputEvent) -> None:
        for handler in self._audio_input_handlers:
            await _maybe_await(handler(event))


async def _maybe_await(result: Awaitable[None] | None) -> None:
    if result is not None:
        await result
