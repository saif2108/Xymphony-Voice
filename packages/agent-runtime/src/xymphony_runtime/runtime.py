"""Provider-agnostic Agent Runtime orchestration core."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from xymphony_contracts import Event
from xymphony_contracts.enums import EventType, MessageRole, SessionEndReason, SessionStatus
from xymphony_contracts.events import TextRange, TranscriptFramePayload
from xymphony_contracts.llm import LLMProvider
from xymphony_contracts.persistence import (
    ConversationRepository,
    ConversationSummaryRepository,
    SessionRepository,
)
from xymphony_contracts.provider import ProviderError
from xymphony_contracts.session import Message
from xymphony_contracts.stt import STTAudioFrame, STTProvider, STTRequest
from xymphony_contracts.tts import TTSProvider, TTSRequest
from xymphony_runtime.cancellation import EventCancellationToken
from xymphony_runtime.context import RuntimeContext
from xymphony_runtime.conversation import build_text_message
from xymphony_runtime.dispatch import (
    agent_interrupted_event,
    error_event,
    llm_response_event,
    llm_token_event,
    session_ended_event,
    session_started_event,
    transcript_frame_event,
    tts_chunk_event,
    user_speech_ended_event,
    user_speech_started_event,
)
from xymphony_runtime.errors import (
    ContextBudgetExceededError,
    InvalidRuntimeInputError,
    InvalidStateTransitionError,
    RuntimeNotRunningError,
    StaleTurnEventError,
)
from xymphony_runtime.input import RuntimeInput, RuntimeInputKind
from xymphony_runtime.llm_config import LLMRuntimeConfig
from xymphony_runtime.llm_context import LLMContextAssembler
from xymphony_runtime.streaming import IncrementalOutputSink, RuntimeStreamChunk
from xymphony_runtime.stt_config import STTRuntimeConfig
from xymphony_runtime.summarization import ConversationSummarizer
from xymphony_runtime.tts_config import TTSRuntimeConfig
from xymphony_runtime.turn import RuntimeTurn

logger = logging.getLogger(__name__)

EventListener = Callable[[Event], None]


class AgentRuntime:
    """Orchestrates turns and runtime events without provider adapters."""

    def __init__(
        self,
        context: RuntimeContext,
        *,
        output_sink: IncrementalOutputSink | None = None,
        llm_provider: LLMProvider | None = None,
        llm_config: LLMRuntimeConfig | None = None,
        stt_provider: STTProvider | None = None,
        stt_config: STTRuntimeConfig | None = None,
        tts_provider: TTSProvider | None = None,
        tts_config: TTSRuntimeConfig | None = None,
        session_repository: SessionRepository | None = None,
        conversation_repository: ConversationRepository | None = None,
        summary_repository: ConversationSummaryRepository | None = None,
    ) -> None:
        self._context = context
        self._output_sink = output_sink
        self._session_repository = session_repository
        self._conversation_repository = conversation_repository
        self._summary_repository = summary_repository
        self._llm_provider = llm_provider
        self._llm_config = llm_config
        self._stt_provider = stt_provider
        self._stt_config = stt_config
        self._tts_provider = tts_provider
        self._tts_config = tts_config
        self._running = False
        self._turns: dict[UUID, RuntimeTurn] = {}
        self._current_turn_id: UUID | None = None
        self._admitted_events: list[Event] = []
        self._active_tasks: set[asyncio.Task[None]] = set()
        self._listeners: list[EventListener] = []
        self._llm_cancel_tokens: dict[UUID, EventCancellationToken] = {}
        self._stt_cancel_tokens: dict[UUID, EventCancellationToken] = {}
        self._stt_audio_queues: dict[UUID, asyncio.Queue[STTAudioFrame | None]] = {}
        self._stt_tasks: dict[UUID, asyncio.Task[None]] = {}
        self._tts_cancel_tokens: dict[UUID, EventCancellationToken] = {}
        self._llm_context_assembler = LLMContextAssembler()
        self._summarizer: ConversationSummarizer | None = None
        if llm_provider is not None and llm_config is not None and summary_repository is not None:
            self._summarizer = ConversationSummarizer(
                llm_provider=llm_provider,
                llm_config=llm_config,
                summary_repository=summary_repository,
            )

    @property
    def context(self) -> RuntimeContext:
        return self._context

    @property
    def running(self) -> bool:
        return self._running

    @property
    def current_turn_id(self) -> UUID | None:
        return self._current_turn_id

    @property
    def current_turn(self) -> RuntimeTurn | None:
        if self._current_turn_id is None:
            return None
        return self._turns.get(self._current_turn_id)

    @property
    def admitted_events(self) -> tuple[Event, ...]:
        return tuple(self._admitted_events)

    @property
    def turns(self) -> tuple[RuntimeTurn, ...]:
        return tuple(self._turns.values())

    @property
    def speech_input_enabled(self) -> bool:
        return self._stt_provider is not None and self._stt_config is not None

    @property
    def voice_output_enabled(self) -> bool:
        return self._tts_provider is not None and self._tts_config is not None

    def on_event(self, listener: EventListener) -> None:
        self._listeners.append(listener)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._context.session_status = SessionStatus.ACTIVE
        self._sync_session_status(SessionStatus.ACTIVE)
        self.admit_event(session_started_event(self._context))
        logger.info("runtime_started", extra={"session_id": str(self._context.session_id)})

    async def stop(self, *, reason: str = "worker_draining") -> None:
        if not self._running:
            return
        self._context.request_shutdown()
        await self._cancel_active_turn()
        await self._cancel_active_tasks()
        self.admit_event(session_ended_event(self._context, reason=reason))
        self._context.session_status = SessionStatus.TERMINATED
        self._sync_session_status(
            SessionStatus.TERMINATED,
            ended_at=datetime.now(tz=UTC),
            end_reason=self._map_stop_reason(reason),
        )
        self._running = False
        self._current_turn_id = None
        logger.info("runtime_stopped", extra={"session_id": str(self._context.session_id)})

    async def handle_input(self, runtime_input: RuntimeInput) -> None:
        if not self._running:
            raise RuntimeNotRunningError("runtime is not running")
        if self._context.shutdown_requested:
            return

        match runtime_input.kind:
            case RuntimeInputKind.TEXT_INPUT:
                await self._handle_text_input(runtime_input)
            case RuntimeInputKind.USER_SPEECH_STARTED:
                await self._handle_user_speech_started()
            case RuntimeInputKind.USER_SPEECH_ENDED:
                await self._handle_user_speech_ended()
            case RuntimeInputKind.AUDIO_FRAME:
                await self._handle_audio_frame(runtime_input)
            case RuntimeInputKind.CANCEL_TURN:
                await self._handle_cancel_turn(runtime_input.turn_id)
            case RuntimeInputKind.SHUTDOWN:
                await self.stop(reason="user_stop")
            case RuntimeInputKind.ERROR:
                await self._handle_error(runtime_input)
            case _:
                raise InvalidRuntimeInputError(f"unsupported input kind: {runtime_input.kind}")

    def admit_event(self, event: Event) -> bool:
        if event.is_stale_for_cancelled_turns(self._context.cancelled_turn_ids):
            logger.info(
                "stale_event_dropped",
                extra={
                    "session_id": str(self._context.session_id),
                    "turn_id": str(event.turn_id) if event.turn_id else None,
                    "event_type": event.type.value,
                },
            )
            return False
        self._admitted_events.append(event)
        for listener in self._listeners:
            listener(event)
        return True

    async def emit_stream_chunk(self, chunk: RuntimeStreamChunk) -> bool:
        if self._context.is_turn_cancelled(chunk.turn_id):
            return False
        if self._output_sink is not None:
            await self._output_sink.emit(chunk)
        return True

    async def _handle_text_input(self, runtime_input: RuntimeInput) -> None:
        if not runtime_input.text or not runtime_input.text.strip():
            raise InvalidRuntimeInputError("text input must be non-empty")
        turn = self._begin_turn()
        logger.info(
            "turn_text_input",
            extra={
                "session_id": str(self._context.session_id),
                "turn_id": str(turn.id),
            },
        )
        if self._llm_provider is None or self._llm_config is None:
            await self._complete_turn(turn)
            return

        await self._run_assistant_pipeline(turn, runtime_input.text.strip())

    async def _run_assistant_pipeline(self, turn: RuntimeTurn, user_text: str) -> None:
        cancel_token = EventCancellationToken()
        self._llm_cancel_tokens[turn.id] = cancel_token
        self._tts_cancel_tokens[turn.id] = cancel_token
        try:
            assistant_text = await self._run_llm_stream(turn, user_text, cancel_token)
            if assistant_text is None or turn.state.is_terminal:
                return
            if self._tts_provider is not None and self._tts_config is not None:
                await self._run_tts_stream(turn, assistant_text, cancel_token)
            if turn.state.is_terminal:
                return
            self._persist_turn_exchange(turn, user_text, assistant_text)
            await self._complete_turn(turn)
        finally:
            self._llm_cancel_tokens.pop(turn.id, None)
            self._tts_cancel_tokens.pop(turn.id, None)

    async def _handle_user_speech_started(self) -> None:
        turn = self._begin_turn()
        self.admit_event(user_speech_started_event(self._context, turn_id=turn.id))
        if self._stt_provider is None or self._stt_config is None:
            return

        queue: asyncio.Queue[STTAudioFrame | None] = asyncio.Queue()
        cancel_token = EventCancellationToken()
        self._stt_audio_queues[turn.id] = queue
        self._stt_cancel_tokens[turn.id] = cancel_token
        task = self._track_task(
            asyncio.create_task(self._run_stt_stream(turn, queue, cancel_token))
        )
        self._stt_tasks[turn.id] = task

    async def _handle_user_speech_ended(self) -> None:
        turn = self.current_turn
        if turn is None or turn.state.is_terminal:
            raise InvalidRuntimeInputError("user speech ended without an active turn")
        self.admit_event(user_speech_ended_event(self._context, turn_id=turn.id))
        final_transcript: str | None = None
        if self._stt_provider is None or self._stt_config is None:
            await self._complete_turn(turn)
            return

        queue = self._stt_audio_queues.get(turn.id)
        if queue is not None:
            await queue.put(None)
        task = self._stt_tasks.get(turn.id)
        if task is not None:
            await task
        self._cleanup_stt_turn(turn.id)
        if turn.state.is_terminal:
            return

        final_transcript = self._final_transcript_for_turn(turn.id)
        if final_transcript and final_transcript.strip():
            logger.info(
                "transcript_finalized",
                extra={
                    "session_id": str(self._context.session_id),
                    "turn_id": str(turn.id),
                    "transcript_length": len(final_transcript.strip()),
                },
            )
            if self._llm_provider is not None and self._llm_config is not None:
                logger.info(
                    "speech_transcript_forwarded",
                    extra={
                        "session_id": str(self._context.session_id),
                        "turn_id": str(turn.id),
                    },
                )
                await self._run_assistant_pipeline(turn, final_transcript.strip())
                return

        await self._complete_turn(turn)

    async def _handle_audio_frame(self, runtime_input: RuntimeInput) -> None:
        if runtime_input.audio_data is None:
            raise InvalidRuntimeInputError("audio frame must include audio_data")
        if runtime_input.audio_duration_ms is None:
            raise InvalidRuntimeInputError("audio frame must include audio_duration_ms")
        turn_id = self._current_turn_id
        if turn_id is None:
            raise InvalidRuntimeInputError("audio frame without an active turn")
        queue = self._stt_audio_queues.get(turn_id)
        if queue is None:
            raise InvalidRuntimeInputError("audio frame without an active stt stream")
        await queue.put(
            STTAudioFrame(
                data=runtime_input.audio_data,
                duration_ms=runtime_input.audio_duration_ms,
                sample_rate_hz=runtime_input.audio_sample_rate_hz or 16_000,
                channels=runtime_input.audio_channels or 1,
            )
        )

    async def _handle_cancel_turn(self, turn_id: UUID | None) -> None:
        target_id = turn_id or self._current_turn_id
        if target_id is None:
            raise InvalidRuntimeInputError("no turn to cancel")
        await self._cancel_turn(target_id)

    async def _handle_error(self, runtime_input: RuntimeInput) -> None:
        code = runtime_input.error_code or "runtime_error"
        message = runtime_input.error_message or "runtime error"
        turn = self.current_turn
        if turn is not None and not turn.state.is_terminal:
            turn.fail(error_code=code)
            self._context.cancel_turn(turn.id)
            self.admit_event(
                error_event(self._context, code=code, message=message, turn_id=turn.id)
            )
            if self._current_turn_id == turn.id:
                self._current_turn_id = None
        else:
            self.admit_event(error_event(self._context, code=code, message=message))

    def _begin_turn(self) -> RuntimeTurn:
        if self._current_turn_id is not None:
            current = self._turns[self._current_turn_id]
            if not current.state.is_terminal:
                raise InvalidRuntimeInputError("a turn is already active")

        turn_id = uuid4()
        turn = RuntimeTurn.create(
            turn_id=turn_id,
            session_id=self._context.session_id,
            organization_id=self._context.organization_id,
            sequence=self._context.next_turn_sequence(),
        )
        turn.activate()
        self._turns[turn_id] = turn
        self._current_turn_id = turn_id
        logger.info(
            "turn_started",
            extra={
                "session_id": str(self._context.session_id),
                "turn_id": str(turn_id),
            },
        )
        return turn

    async def _complete_turn(self, turn: RuntimeTurn) -> None:
        if turn.state.is_terminal:
            raise InvalidStateTransitionError(f"turn {turn.id} is already terminal")
        if self._context.is_turn_cancelled(turn.id):
            raise StaleTurnEventError(f"turn {turn.id} is cancelled")
        turn.complete()
        if self._current_turn_id == turn.id:
            self._current_turn_id = None
        logger.info(
            "turn_completed",
            extra={
                "session_id": str(self._context.session_id),
                "turn_id": str(turn.id),
            },
        )

    async def _cancel_turn(self, turn_id: UUID) -> None:
        turn = self._turns.get(turn_id)
        if turn is None:
            raise InvalidRuntimeInputError(f"unknown turn_id: {turn_id}")
        if turn.state.is_terminal:
            return
        cancel_token = self._llm_cancel_tokens.get(turn_id)
        if cancel_token is not None:
            cancel_token.cancel()
        stt_cancel_token = self._stt_cancel_tokens.get(turn_id)
        if stt_cancel_token is not None:
            stt_cancel_token.cancel()
        tts_cancel_token = self._tts_cancel_tokens.get(turn_id)
        if tts_cancel_token is not None:
            tts_cancel_token.cancel()
        self._context.cancel_turn(turn_id)
        turn.cancel()
        self.admit_event(agent_interrupted_event(self._context, turn_id=turn_id))
        if self._current_turn_id == turn_id:
            self._current_turn_id = None
        logger.info(
            "turn_cancelled",
            extra={
                "session_id": str(self._context.session_id),
                "turn_id": str(turn_id),
            },
        )

    async def _cancel_active_turn(self) -> None:
        if self._current_turn_id is None:
            return
        turn = self._turns.get(self._current_turn_id)
        if turn is not None and not turn.state.is_terminal:
            await self._cancel_turn(turn.id)

    def _track_task(self, task: asyncio.Task[None]) -> asyncio.Task[None]:
        self._active_tasks.add(task)

        def _done(completed: asyncio.Task[None]) -> None:
            self._active_tasks.discard(completed)

        task.add_done_callback(_done)
        return task

    async def _cancel_active_tasks(self) -> None:
        pending = [task for task in self._active_tasks if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    async def _run_llm_stream(
        self,
        turn: RuntimeTurn,
        text: str,
        cancel: EventCancellationToken,
    ) -> str | None:
        if self._llm_provider is None or self._llm_config is None:
            return None

        history = self._conversation_messages()
        summary_text: str | None = None
        assembly_history = history
        if self._summarizer is not None:
            preparation = await self._summarizer.prepare(
                session_id=self._context.session_id,
                organization_id=self._context.organization_id,
                agent_version_id=self._context.agent_version_id,
                history=history,
                current_user_text=text,
                cancel=cancel,
                is_turn_cancelled=lambda: self._context.is_turn_cancelled(turn.id),
            )
            if cancel.cancelled or self._context.is_turn_cancelled(turn.id):
                return None
            summary_text = preparation.summary_text
            assembly_history = preparation.history_for_assembly

        try:
            request = self._llm_context_assembler.assemble(
                history=assembly_history,
                current_user_text=text,
                config=self._llm_config,
                summary_text=summary_text,
            )
        except ContextBudgetExceededError as exc:
            turn.fail(error_code="context_budget_exceeded")
            self.admit_event(
                error_event(
                    self._context,
                    code="context_budget_exceeded",
                    message=str(exc),
                    turn_id=turn.id,
                    retryable=False,
                )
            )
            if self._current_turn_id == turn.id:
                self._current_turn_id = None
            logger.info(
                "context_budget_exceeded",
                extra={
                    "session_id": str(self._context.session_id),
                    "turn_id": str(turn.id),
                    "error_message": str(exc),
                },
            )
            return None
        full_text_parts: list[str] = []
        finish_reason = "stop"
        logger.info(
            "llm_started",
            extra={
                "session_id": str(self._context.session_id),
                "turn_id": str(turn.id),
                "provider_key": self._llm_config.provider_key,
            },
        )

        try:
            async for chunk in self._llm_provider.stream(request, cancel=cancel):
                if cancel.cancelled or self._context.is_turn_cancelled(turn.id):
                    return None
                if chunk.delta:
                    full_text_parts.append(chunk.delta)
                    self.admit_event(
                        llm_token_event(self._context, turn_id=turn.id, delta=chunk.delta)
                    )
                if chunk.finish_reason:
                    finish_reason = chunk.finish_reason
        except ProviderError as exc:
            if cancel.cancelled or self._context.is_turn_cancelled(turn.id):
                return None
            turn.fail(error_code=exc.code.value)
            self.admit_event(
                error_event(
                    self._context,
                    code=exc.code.value,
                    message=exc.message,
                    turn_id=turn.id,
                    retryable=exc.retryable,
                )
            )
            if self._current_turn_id == turn.id:
                self._current_turn_id = None
            logger.info(
                "llm_provider_error",
                extra={
                    "session_id": str(self._context.session_id),
                    "turn_id": str(turn.id),
                    "error_code": exc.code.value,
                    "provider_key": exc.provider_key,
                },
            )
            return None

        if cancel.cancelled or self._context.is_turn_cancelled(turn.id):
            return None

        full_text = "".join(full_text_parts)
        self.admit_event(
            llm_response_event(
                self._context,
                turn_id=turn.id,
                text=full_text,
                finish_reason=finish_reason,
            )
        )
        logger.info(
            "llm_completed",
            extra={
                "session_id": str(self._context.session_id),
                "turn_id": str(turn.id),
            },
        )
        return full_text

    async def _run_tts_stream(
        self,
        turn: RuntimeTurn,
        text: str,
        cancel: EventCancellationToken,
    ) -> None:
        if self._tts_provider is None or self._tts_config is None:
            return

        request = TTSRequest(
            provider_key=self._tts_config.provider_key,
            voice_ref=self._tts_config.voice_ref,
            text=text,
            params=self._tts_config.params,
        )
        logger.info(
            "tts_started",
            extra={
                "session_id": str(self._context.session_id),
                "turn_id": str(turn.id),
                "provider_key": self._tts_config.provider_key,
            },
        )

        try:
            async for chunk in self._tts_provider.stream(request, cancel=cancel):
                if cancel.cancelled or self._context.is_turn_cancelled(turn.id):
                    return
                text_range = None
                if chunk.text_range is not None:
                    text_range = TextRange(
                        start=chunk.text_range.start,
                        end=chunk.text_range.end,
                    )
                self.admit_event(
                    tts_chunk_event(
                        self._context,
                        turn_id=turn.id,
                        audio_ref=chunk.audio_ref,
                        text_range=text_range,
                    )
                )
            if cancel.cancelled or self._context.is_turn_cancelled(turn.id):
                return
            logger.info(
                "tts_completed",
                extra={
                    "session_id": str(self._context.session_id),
                    "turn_id": str(turn.id),
                },
            )
        except ProviderError as exc:
            if cancel.cancelled or self._context.is_turn_cancelled(turn.id):
                return
            turn.fail(error_code=exc.code.value)
            self.admit_event(
                error_event(
                    self._context,
                    code=exc.code.value,
                    message=exc.message,
                    turn_id=turn.id,
                    retryable=exc.retryable,
                )
            )
            if self._current_turn_id == turn.id:
                self._current_turn_id = None
            logger.info(
                "tts_provider_error",
                extra={
                    "session_id": str(self._context.session_id),
                    "turn_id": str(turn.id),
                    "error_code": exc.code.value,
                    "provider_key": exc.provider_key,
                },
            )

    async def _audio_from_queue(
        self,
        queue: asyncio.Queue[STTAudioFrame | None],
        cancel: EventCancellationToken,
    ) -> AsyncIterator[STTAudioFrame]:
        while True:
            if cancel.cancelled:
                return
            frame = await queue.get()
            if frame is None:
                return
            yield frame

    def _cleanup_stt_turn(self, turn_id: UUID) -> None:
        self._stt_audio_queues.pop(turn_id, None)
        self._stt_tasks.pop(turn_id, None)
        self._stt_cancel_tokens.pop(turn_id, None)

    async def _run_stt_stream(
        self,
        turn: RuntimeTurn,
        queue: asyncio.Queue[STTAudioFrame | None],
        cancel: EventCancellationToken,
    ) -> None:
        if self._stt_provider is None or self._stt_config is None:
            return

        request = STTRequest(
            provider_key=self._stt_config.provider_key,
            model=self._stt_config.model,
            language=self._stt_config.language,
            params=self._stt_config.params,
        )

        try:
            audio = self._audio_from_queue(queue, cancel)
            async for chunk in self._stt_provider.transcribe(request, audio, cancel=cancel):
                if cancel.cancelled or self._context.is_turn_cancelled(turn.id):
                    return
                self.admit_event(
                    transcript_frame_event(
                        self._context,
                        turn_id=turn.id,
                        text=chunk.text,
                        is_final=chunk.is_final,
                        start_ms=chunk.start_ms,
                        end_ms=chunk.end_ms,
                        confidence=chunk.confidence,
                    )
                )
        except ProviderError as exc:
            if cancel.cancelled or self._context.is_turn_cancelled(turn.id):
                return
            turn.fail(error_code=exc.code.value)
            self.admit_event(
                error_event(
                    self._context,
                    code=exc.code.value,
                    message=exc.message,
                    turn_id=turn.id,
                    retryable=exc.retryable,
                )
            )
            if self._current_turn_id == turn.id:
                self._current_turn_id = None
            logger.info(
                "stt_provider_error",
                extra={
                    "session_id": str(self._context.session_id),
                    "turn_id": str(turn.id),
                    "error_code": exc.code.value,
                    "provider_key": exc.provider_key,
                },
            )

    def _final_transcript_for_turn(self, turn_id: UUID) -> str | None:
        final_text: str | None = None
        for event in self._admitted_events:
            if event.turn_id != turn_id or event.type != EventType.TRANSCRIPT_FRAME:
                continue
            payload = event.payload
            if isinstance(payload, TranscriptFramePayload) and payload.is_final:
                final_text = payload.text
        return final_text

    def _conversation_messages(self) -> tuple[Message, ...]:
        if self._conversation_repository is None:
            return ()
        return self._conversation_repository.list_messages(
            self._context.session_id,
            organization_id=self._context.organization_id,
        )

    def _persist_turn_exchange(
        self,
        turn: RuntimeTurn,
        user_text: str,
        assistant_text: str,
    ) -> None:
        if self._conversation_repository is None:
            return
        if self._context.is_turn_cancelled(turn.id):
            return
        user_message = build_text_message(
            session_id=self._context.session_id,
            turn_id=turn.id,
            organization_id=self._context.organization_id,
            role=MessageRole.USER,
            text=user_text,
        )
        assistant_message = build_text_message(
            session_id=self._context.session_id,
            turn_id=turn.id,
            organization_id=self._context.organization_id,
            role=MessageRole.ASSISTANT,
            text=assistant_text,
        )
        self._conversation_repository.append_message(user_message)
        self._conversation_repository.append_message(assistant_message)
        logger.info(
            "conversation_turn_persisted",
            extra={
                "session_id": str(self._context.session_id),
                "turn_id": str(turn.id),
            },
        )

    def _sync_session_status(
        self,
        status: SessionStatus,
        *,
        ended_at: datetime | None = None,
        end_reason: SessionEndReason | None = None,
    ) -> None:
        if self._session_repository is None:
            return
        session = self._session_repository.get_session(
            self._context.session_id,
            organization_id=self._context.organization_id,
            project_id=self._context.project_id,
        )
        if session is None:
            return
        updates: dict[str, object] = {"status": status}
        if ended_at is not None:
            updates["ended_at"] = ended_at
        if end_reason is not None:
            updates["end_reason"] = end_reason
        self._session_repository.update_session(session.model_copy(update=updates))

    @staticmethod
    def _map_stop_reason(reason: str) -> SessionEndReason:
        mapping = {
            "user_stop": SessionEndReason.USER_STOP,
            "worker_draining": SessionEndReason.WORKER_DRAINING,
            "disconnect": SessionEndReason.DISCONNECT,
            "error": SessionEndReason.ERROR,
        }
        return mapping.get(reason, SessionEndReason.ERROR)
