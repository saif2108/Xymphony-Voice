"""Provider-agnostic Agent Runtime orchestration core."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from uuid import UUID, uuid4

from xymphony_contracts import Event
from xymphony_contracts.enums import SessionStatus
from xymphony_contracts.llm import LLMMessage, LLMProvider, LLMRequest, LLMRole, ProviderError
from xymphony_runtime.cancellation import EventCancellationToken
from xymphony_runtime.context import RuntimeContext
from xymphony_runtime.dispatch import (
    agent_interrupted_event,
    error_event,
    llm_response_event,
    llm_token_event,
    session_ended_event,
    session_started_event,
    user_speech_ended_event,
    user_speech_started_event,
)
from xymphony_runtime.errors import (
    InvalidRuntimeInputError,
    InvalidStateTransitionError,
    RuntimeNotRunningError,
    StaleTurnEventError,
)
from xymphony_runtime.input import RuntimeInput, RuntimeInputKind
from xymphony_runtime.llm_config import LLMRuntimeConfig
from xymphony_runtime.streaming import IncrementalOutputSink, RuntimeStreamChunk
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
    ) -> None:
        self._context = context
        self._output_sink = output_sink
        self._llm_provider = llm_provider
        self._llm_config = llm_config
        self._running = False
        self._turns: dict[UUID, RuntimeTurn] = {}
        self._current_turn_id: UUID | None = None
        self._admitted_events: list[Event] = []
        self._active_tasks: set[asyncio.Task[None]] = set()
        self._listeners: list[EventListener] = []
        self._llm_cancel_tokens: dict[UUID, EventCancellationToken] = {}

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

    def on_event(self, listener: EventListener) -> None:
        self._listeners.append(listener)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._context.session_status = SessionStatus.ACTIVE
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

        cancel_token = EventCancellationToken()
        self._llm_cancel_tokens[turn.id] = cancel_token
        try:
            await self._run_llm_stream(turn, runtime_input.text.strip(), cancel_token)
        finally:
            self._llm_cancel_tokens.pop(turn.id, None)

    async def _handle_user_speech_started(self) -> None:
        turn = self._begin_turn()
        self.admit_event(user_speech_started_event(self._context, turn_id=turn.id))

    async def _handle_user_speech_ended(self) -> None:
        turn = self.current_turn
        if turn is None or turn.state.is_terminal:
            raise InvalidRuntimeInputError("user speech ended without an active turn")
        self.admit_event(user_speech_ended_event(self._context, turn_id=turn.id))
        await self._complete_turn(turn)

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
    ) -> None:
        if self._llm_provider is None or self._llm_config is None:
            return

        request = LLMRequest(
            provider_key=self._llm_config.provider_key,
            model=self._llm_config.model,
            messages=(LLMMessage(role=LLMRole.USER, content=text),),
            system=self._llm_config.system_instructions,
            params=self._llm_config.params,
        )
        full_text_parts: list[str] = []
        finish_reason = "stop"

        try:
            async for chunk in self._llm_provider.stream(request, cancel=cancel):
                if cancel.cancelled or self._context.is_turn_cancelled(turn.id):
                    return
                if chunk.delta:
                    full_text_parts.append(chunk.delta)
                    self.admit_event(
                        llm_token_event(self._context, turn_id=turn.id, delta=chunk.delta)
                    )
                if chunk.finish_reason:
                    finish_reason = chunk.finish_reason
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
                "llm_provider_error",
                extra={
                    "session_id": str(self._context.session_id),
                    "turn_id": str(turn.id),
                    "error_code": exc.code.value,
                    "provider_key": exc.provider_key,
                },
            )
            return

        if cancel.cancelled or self._context.is_turn_cancelled(turn.id):
            return

        full_text = "".join(full_text_parts)
        self.admit_event(
            llm_response_event(
                self._context,
                turn_id=turn.id,
                text=full_text,
                finish_reason=finish_reason,
            )
        )
        await self._complete_turn(turn)
