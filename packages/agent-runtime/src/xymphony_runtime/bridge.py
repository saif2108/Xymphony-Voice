"""Bridge between MediaTransport and AgentRuntime (Phase 2 Step 6)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import cast

from xymphony_contracts import Event
from xymphony_contracts.enums import EventType
from xymphony_contracts.events import TTSChunkPayload
from xymphony_contracts.media_transport import (
    MediaTransport,
    MediaTransportConfig,
    TransportAudioFrame,
    TransportAudioInputEvent,
    TransportAudioInputKind,
    TransportAudioOutputFrame,
    TransportConnectionState,
    TransportErrorEvent,
    TransportParticipantEvent,
)
from xymphony_contracts.tts import TTSOutputAudioResolver
from xymphony_runtime.errors import RuntimeNotRunningError
from xymphony_runtime.input import RuntimeInput
from xymphony_runtime.lifecycle import RuntimeSessionLifecycleState
from xymphony_runtime.observations import RuntimeObservation, lifecycle_transition
from xymphony_runtime.runtime import AgentRuntime

logger = logging.getLogger(__name__)

RuntimeEventHandler = Callable[[Event], None]

_ASSISTANT_OUTPUT_EVENT_TYPES = frozenset(
    {
        EventType.LLM_TOKEN,
        EventType.LLM_RESPONSE,
        EventType.TTS_CHUNK,
    }
)


class RuntimeMediaBridge:
    """Transport-agnostic adapter connecting MediaTransport to AgentRuntime."""

    def __init__(
        self,
        *,
        runtime: AgentRuntime,
        transport: MediaTransport,
        tts_output_resolver: TTSOutputAudioResolver | None = None,
    ) -> None:
        self._runtime = runtime
        self._transport = transport
        self._tts_output_resolver = tts_output_resolver
        self._shutdown = asyncio.Event()
        self._lifecycle_state = RuntimeSessionLifecycleState.INITIALIZING
        self._observations: list[RuntimeObservation] = []
        self._runtime_events: list[Event] = []
        self._runtime_event_handlers: list[RuntimeEventHandler] = []
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._runtime_listener_registered = False
        self._transport_handlers_registered = False
        self._output_chunk_indexes: dict[str, int] = {}
        self._transport_config: MediaTransportConfig | None = None
        self.connection_states: list[TransportConnectionState] = []
        self.participant_events: list[TransportParticipantEvent] = []
        self.errors: list[TransportErrorEvent] = []

    @property
    def runtime(self) -> AgentRuntime:
        return self._runtime

    @property
    def transport(self) -> MediaTransport:
        return self._transport

    @property
    def lifecycle_state(self) -> RuntimeSessionLifecycleState:
        return self._lifecycle_state

    @property
    def observations(self) -> tuple[RuntimeObservation, ...]:
        return tuple(self._observations)

    @property
    def runtime_events(self) -> tuple[Event, ...]:
        return tuple(self._runtime_events)

    @property
    def assistant_output_events(self) -> tuple[Event, ...]:
        return tuple(
            event for event in self._runtime_events if event.type in _ASSISTANT_OUTPUT_EVENT_TYPES
        )

    @property
    def published_output_frames(self) -> tuple[TransportAudioOutputFrame, ...]:
        publish = getattr(self._transport, "published_output_frames", None)
        if isinstance(publish, list):
            return tuple(publish)
        return ()

    def on_runtime_event(self, handler: RuntimeEventHandler) -> None:
        self._runtime_event_handlers.append(handler)

    async def run(self, config: MediaTransportConfig) -> None:
        wait_tasks: list[asyncio.Task[None]] = []
        self._transition(RuntimeSessionLifecycleState.INITIALIZING)
        self._register_transport_handlers()
        self._register_runtime_listener()

        logger.info(
            "bridge_starting",
            extra={
                "session_id": str(self._runtime.context.session_id),
                "room": config.room_name,
            },
        )
        try:
            await self._runtime.start()
            self._transition(RuntimeSessionLifecycleState.CONNECTING)
            self._transport_config = config
            await self._transport.connect(config)
            self._transition(RuntimeSessionLifecycleState.CONNECTED)

            disconnect_task = self._track_task(
                asyncio.create_task(
                    self._transport.wait_until_disconnected(),
                    name=f"bridge-{self._runtime.context.session_id}-wait-disconnect",
                )
            )
            shutdown_task = self._track_task(
                asyncio.create_task(
                    self._wait_for_shutdown(),
                    name=f"bridge-{self._runtime.context.session_id}-wait-shutdown",
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
            await self._handle_connect_failure(str(exc))
            logger.exception(
                "bridge_connect_failed",
                extra={"session_id": str(self._runtime.context.session_id)},
            )
        else:
            if self._shutdown.is_set():
                self._transition(RuntimeSessionLifecycleState.STOPPING)
        finally:
            await self._teardown(wait_tasks)

    async def shutdown(self) -> None:
        self._shutdown.set()

    async def handle_input(self, runtime_input: RuntimeInput) -> None:
        if not self._runtime.running:
            raise RuntimeNotRunningError("runtime is not running")
        await self._runtime.handle_input(runtime_input)

    def _register_transport_handlers(self) -> None:
        if self._transport_handlers_registered:
            return
        self._transport_handlers_registered = True
        self._transport.on_connection_state(self._on_connection_state)
        self._transport.on_participant_event(self._on_participant_event)
        self._transport.on_error(self._on_transport_error)
        self._transport.on_audio_input(self._on_transport_audio_input)
        self._transport.on_audio_frame(self._on_transport_audio_frame)

    def _register_runtime_listener(self) -> None:
        if self._runtime_listener_registered:
            return
        self._runtime_listener_registered = True

        def _listener(event: Event) -> None:
            self._runtime_events.append(event)
            for handler in self._runtime_event_handlers:
                handler(event)
            if event.type == EventType.TTS_CHUNK:
                self._track_task(asyncio.create_task(self._publish_tts_output(event)))

        self._runtime.on_event(_listener)

    async def _publish_tts_output(self, event: Event) -> None:
        if not self._voice_output_enabled():
            return
        if event.turn_id is None:
            return
        if self._runtime.context.is_turn_cancelled(event.turn_id):
            return
        payload = event.payload
        if not isinstance(payload, TTSChunkPayload):
            return
        resolver = self._resolve_tts_output_audio()
        if resolver is None:
            return
        audio = resolver.resolve_output_audio(payload.audio_ref)
        if audio is None:
            logger.info(
                "bridge_tts_output_unresolved",
                extra={
                    "session_id": str(self._runtime.context.session_id),
                    "turn_id": str(event.turn_id),
                    "audio_ref": payload.audio_ref,
                },
            )
            return
        turn_key = str(event.turn_id)
        chunk_index = self._output_chunk_indexes.get(turn_key, 0)
        self._output_chunk_indexes[turn_key] = chunk_index + 1
        room_name = self._transport_config.room_name if self._transport_config else ""
        output_frame = TransportAudioOutputFrame(
            room_name=room_name,
            data=audio.data,
            sample_rate_hz=audio.sample_rate_hz,
            channels=audio.channels,
            duration_ms=audio.duration_ms,
            chunk_index=chunk_index,
            turn_id=turn_key,
        )
        logger.info(
            "bridge_tts_output_published",
            extra={
                "session_id": str(self._runtime.context.session_id),
                "turn_id": turn_key,
                "chunk_index": chunk_index,
                "duration_ms": audio.duration_ms,
            },
        )
        await self._transport.publish_audio_output(output_frame)

    def _resolve_tts_output_audio(self) -> TTSOutputAudioResolver | None:
        if self._tts_output_resolver is not None:
            return self._tts_output_resolver
        provider = getattr(self._runtime, "_tts_provider", None)
        if provider is not None and hasattr(provider, "resolve_output_audio"):
            return cast(TTSOutputAudioResolver, provider)
        return None

    def _voice_output_enabled(self) -> bool:
        return (
            self._runtime.running
            and not self._runtime.context.shutdown_requested
            and self._runtime.voice_output_enabled
            and self._resolve_tts_output_audio() is not None
        )

    async def _wait_for_shutdown(self) -> None:
        await self._shutdown.wait()

    async def _on_connection_state(self, state: TransportConnectionState) -> None:
        self.connection_states.append(state)
        logger.info(
            "bridge_transport_state",
            extra={
                "session_id": str(self._runtime.context.session_id),
                "state": state.value,
            },
        )

    async def _on_participant_event(self, event: TransportParticipantEvent) -> None:
        self.participant_events.append(event)
        self._observations.append(event)
        logger.info(
            "bridge_participant_event",
            extra={
                "session_id": str(self._runtime.context.session_id),
                "kind": event.kind.value,
                "identity": event.identity,
            },
        )

    async def _on_transport_audio_input(self, event: TransportAudioInputEvent) -> None:
        if not self._voice_input_enabled():
            return
        if event.kind == TransportAudioInputKind.STARTED:
            current_turn = self._runtime.current_turn
            if current_turn is not None and not current_turn.state.is_terminal:
                logger.info(
                    "bridge_audio_input_started_ignored",
                    extra={
                        "session_id": str(self._runtime.context.session_id),
                        "participant": event.participant_identity,
                    },
                )
                return
            logger.info(
                "bridge_audio_input_started",
                extra={
                    "session_id": str(self._runtime.context.session_id),
                    "participant": event.participant_identity,
                },
            )
            await self._runtime.handle_input(RuntimeInput.user_speech_started())
            return

        turn = self._runtime.current_turn
        if turn is None or turn.state.is_terminal:
            logger.info(
                "bridge_audio_input_ended_ignored",
                extra={
                    "session_id": str(self._runtime.context.session_id),
                    "participant": event.participant_identity,
                },
            )
            return
        logger.info(
            "bridge_audio_input_ended",
            extra={
                "session_id": str(self._runtime.context.session_id),
                "participant": event.participant_identity,
            },
        )
        await self._runtime.handle_input(RuntimeInput.user_speech_ended())

    async def _on_transport_audio_frame(self, frame: TransportAudioFrame) -> None:
        if not self._voice_input_enabled():
            return
        turn = self._runtime.current_turn
        if turn is None or turn.state.is_terminal:
            return
        logger.info(
            "bridge_audio_frame_received",
            extra={
                "session_id": str(self._runtime.context.session_id),
                "participant": frame.participant_identity,
                "duration_ms": frame.duration_ms,
                "sample_rate_hz": frame.sample_rate_hz,
            },
        )
        await self._runtime.handle_input(
            RuntimeInput.audio_frame(
                frame.data,
                duration_ms=frame.duration_ms,
                sample_rate_hz=frame.sample_rate_hz,
                channels=frame.channels,
            )
        )

    def _voice_input_enabled(self) -> bool:
        return (
            self._runtime.running
            and not self._runtime.context.shutdown_requested
            and self._runtime.speech_input_enabled
        )

    async def _on_transport_error(self, event: TransportErrorEvent) -> None:
        self._record_transport_error(event)
        if self._runtime.running:
            await self._runtime.handle_input(
                RuntimeInput.error(code=event.code, message=event.message)
            )
        if self._lifecycle_state not in {
            RuntimeSessionLifecycleState.STOPPING,
            RuntimeSessionLifecycleState.STOPPED,
        }:
            self._transition(RuntimeSessionLifecycleState.FAILED)

    async def _handle_connect_failure(self, message: str) -> None:
        if self._lifecycle_state == RuntimeSessionLifecycleState.FAILED:
            return
        event = TransportErrorEvent(
            code="session_connect_failed",
            message=message,
            retryable=False,
        )
        self._record_transport_error(event)
        if self._runtime.running:
            await self._runtime.handle_input(
                RuntimeInput.error(code=event.code, message=event.message)
            )
        self._transition(RuntimeSessionLifecycleState.FAILED)

    def _record_transport_error(self, event: TransportErrorEvent) -> None:
        self.errors.append(event)
        self._observations.append(event)
        logger.error(
            "bridge_transport_error",
            extra={
                "session_id": str(self._runtime.context.session_id),
                "code": event.code,
                "error_message": event.message,
            },
        )

    async def _teardown(self, wait_tasks: list[asyncio.Task[None]]) -> None:
        await self._cancel_tasks(wait_tasks)
        if self._lifecycle_state not in {
            RuntimeSessionLifecycleState.FAILED,
            RuntimeSessionLifecycleState.STOPPING,
        }:
            self._transition(RuntimeSessionLifecycleState.STOPPING)
        if self._runtime.running:
            await self._runtime.stop(reason="transport_session_ended")
        try:
            if self._transport.connection_state != TransportConnectionState.DISCONNECTED:
                await self._transport.disconnect()
        finally:
            if self._lifecycle_state != RuntimeSessionLifecycleState.FAILED:
                self._transition(RuntimeSessionLifecycleState.STOPPED)
            logger.info(
                "bridge_ended",
                extra={
                    "session_id": str(self._runtime.context.session_id),
                    "lifecycle_state": self._lifecycle_state.value,
                },
            )

    def _transition(self, state: RuntimeSessionLifecycleState) -> None:
        self._lifecycle_state = state
        transition = lifecycle_transition(state)
        self._observations.append(transition)
        logger.info(
            "bridge_lifecycle_state",
            extra={
                "session_id": str(self._runtime.context.session_id),
                "state": state.value,
            },
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
