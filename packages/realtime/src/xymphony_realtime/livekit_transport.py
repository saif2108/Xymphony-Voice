"""LiveKit rtc.Room adapter implementing MediaTransport. Not LiveKit Agents."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from typing import cast

from livekit import rtc

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
        self._audio_frame_handlers: list[AudioFrameHandler] = []
        self._audio_input_handlers: list[AudioInputHandler] = []
        self._disconnect_event = asyncio.Event()
        self._handlers_registered = False
        self._audio_tasks: dict[str, asyncio.Task[None]] = {}
        self._audio_source: rtc.AudioSource | None = None
        self._local_audio_track: rtc.LocalAudioTrack | None = None
        self._output_sample_rate_hz = 16_000
        self._output_channels = 1

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

    def on_audio_frame(self, handler: AudioFrameHandler) -> None:
        self._audio_frame_handlers.append(handler)

    def on_audio_input(self, handler: AudioInputHandler) -> None:
        self._audio_input_handlers.append(handler)

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
        await self._setup_outgoing_audio(config)
        logger.info(
            "livekit_connected",
            extra={"room": config.room_name, "identity": config.participant_identity},
        )

    async def disconnect(self) -> None:
        if self._state == TransportConnectionState.DISCONNECTED:
            return
        await self._cancel_audio_tasks()
        await self._teardown_outgoing_audio()
        try:
            await self._room.disconnect()
        finally:
            await self._set_state(TransportConnectionState.DISCONNECTED)
            self._disconnect_event.set()
            logger.info("livekit_disconnected")

    async def wait_until_disconnected(self) -> None:
        await self._disconnect_event.wait()

    async def publish_audio_output(self, frame: TransportAudioOutputFrame) -> None:
        if self._audio_source is None:
            return
        bytes_per_sample = 2 * frame.channels
        if bytes_per_sample <= 0 or len(frame.data) < bytes_per_sample:
            return
        samples_per_channel = len(frame.data) // bytes_per_sample
        lk_frame = rtc.AudioFrame(
            data=frame.data,
            sample_rate=frame.sample_rate_hz,
            num_channels=frame.channels,
            samples_per_channel=samples_per_channel,
        )
        await self._audio_source.capture_frame(lk_frame)
        logger.info(
            "livekit_audio_output_published",
            extra={
                "room": frame.room_name,
                "chunk_index": frame.chunk_index,
                "duration_ms": frame.duration_ms,
            },
        )

    async def _setup_outgoing_audio(self, config: MediaTransportConfig) -> None:
        self._audio_source = rtc.AudioSource(self._output_sample_rate_hz, self._output_channels)
        self._local_audio_track = rtc.LocalAudioTrack.create_audio_track(
            "agent-voice",
            self._audio_source,
        )
        options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        await self._room.local_participant.publish_track(self._local_audio_track, options)
        logger.info(
            "livekit_outgoing_audio_ready",
            extra={"room": config.room_name, "identity": config.participant_identity},
        )

    async def _teardown_outgoing_audio(self) -> None:
        self._audio_source = None
        self._local_audio_track = None

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

        @self._room.on("track_subscribed")
        def _on_track_subscribed(
            track: rtc.Track,
            publication: rtc.RemoteTrackPublication,
            participant: rtc.RemoteParticipant,
        ) -> None:
            if track.kind != rtc.TrackKind.KIND_AUDIO:
                return
            task = asyncio.create_task(self._consume_remote_audio(track, participant))
            self._audio_tasks[track.sid] = task

            def _remove_audio_task(completed: asyncio.Task[None]) -> None:
                self._audio_tasks.pop(track.sid, None)

            task.add_done_callback(_remove_audio_task)

        @self._room.on("track_unsubscribed")
        def _on_track_unsubscribed(
            track: rtc.Track,
            publication: rtc.RemoteTrackPublication,
            participant: rtc.RemoteParticipant,
        ) -> None:
            task = self._audio_tasks.pop(track.sid, None)
            if task is not None and not task.done():
                task.cancel()

    async def _consume_remote_audio(
        self,
        track: rtc.Track,
        participant: rtc.RemoteParticipant,
    ) -> None:
        room_name = self._config.room_name if self._config else ""
        identity = participant.identity
        await self._emit_audio_input(
            TransportAudioInputEvent(
                kind=TransportAudioInputKind.STARTED,
                participant_identity=identity,
                room_name=room_name,
            )
        )
        logger.info(
            "livekit_audio_input_started",
            extra={"participant": identity, "room": room_name},
        )
        try:
            stream = rtc.AudioStream(track, sample_rate=16_000, num_channels=1)
            async for frame_event in stream:
                if self._state == TransportConnectionState.DISCONNECTED:
                    break
                frame = frame_event.frame
                sample_rate = frame.sample_rate or 16_000
                channels = frame.num_channels or 1
                samples = frame.samples_per_channel
                duration_ms = int(samples * 1000 / sample_rate) if sample_rate else 0
                await self._emit_audio_frame(
                    TransportAudioFrame(
                        participant_identity=identity,
                        room_name=room_name,
                        data=bytes(frame.data),
                        sample_rate_hz=sample_rate,
                        channels=channels,
                        duration_ms=duration_ms,
                    )
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._emit_error("audio_ingestion_failed", str(exc), retryable=False)
            logger.exception(
                "livekit_audio_ingestion_failed",
                extra={"participant": identity, "room": room_name},
            )
        finally:
            await self._emit_audio_input(
                TransportAudioInputEvent(
                    kind=TransportAudioInputKind.ENDED,
                    participant_identity=identity,
                    room_name=room_name,
                )
            )
            logger.info(
                "livekit_audio_input_ended",
                extra={"participant": identity, "room": room_name},
            )

    async def _cancel_audio_tasks(self) -> None:
        tasks = list(self._audio_tasks.values())
        self._audio_tasks.clear()
        for task in tasks:
            if task.done():
                continue
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _handle_room_disconnected(self) -> None:
        await self._cancel_audio_tasks()
        await self._teardown_outgoing_audio()
        await self._set_state(TransportConnectionState.DISCONNECTED)
        self._disconnect_event.set()

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
