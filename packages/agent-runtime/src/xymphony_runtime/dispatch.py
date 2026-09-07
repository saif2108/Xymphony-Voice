"""Build contract Event envelopes from runtime context."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from xymphony_contracts import Event
from xymphony_contracts.enums import EventSource, EventType, InterruptReason
from xymphony_contracts.events import (
    AgentInterruptedPayload,
    ErrorPayload,
    EventPayload,
    LLMResponsePayload,
    LLMTokenPayload,
    SessionEndedPayload,
    SessionStartedPayload,
    UserSpeechEndedPayload,
    UserSpeechStartedPayload,
)
from xymphony_contracts.usage import Usage
from xymphony_runtime.context import RuntimeContext


def build_event(
    context: RuntimeContext,
    *,
    event_type: EventType,
    payload: EventPayload,
    turn_id: UUID | None = None,
    source: EventSource = EventSource.RUNTIME,
    correlation_id: UUID | None = None,
    causation_id: UUID | None = None,
) -> Event:
    return Event(
        id=uuid4(),
        type=event_type,
        timestamp=datetime.now(UTC),
        session_id=context.session_id,
        organization_id=context.organization_id,
        project_id=context.project_id,
        agent_id=context.agent_id,
        agent_version_id=context.agent_version_id,
        deployment_id=context.deployment_id,
        turn_id=turn_id,
        sequence=context.next_event_sequence(),
        source=source,
        correlation_id=correlation_id or context.session_id,
        causation_id=causation_id,
        payload=payload,
    )


def session_started_event(context: RuntimeContext) -> Event:
    return build_event(
        context,
        event_type=EventType.SESSION_STARTED,
        payload=SessionStartedPayload(),
        source=EventSource.SYSTEM,
    )


def session_ended_event(context: RuntimeContext, *, reason: str) -> Event:
    return build_event(
        context,
        event_type=EventType.SESSION_ENDED,
        payload=SessionEndedPayload(reason=reason),
        source=EventSource.SYSTEM,
    )


def user_speech_started_event(context: RuntimeContext, *, turn_id: UUID) -> Event:
    return build_event(
        context,
        event_type=EventType.USER_SPEECH_STARTED,
        payload=UserSpeechStartedPayload(),
        turn_id=turn_id,
        source=EventSource.VAD,
    )


def user_speech_ended_event(
    context: RuntimeContext,
    *,
    turn_id: UUID,
    duration_ms: int = 0,
) -> Event:
    return build_event(
        context,
        event_type=EventType.USER_SPEECH_ENDED,
        payload=UserSpeechEndedPayload(duration_ms=duration_ms),
        turn_id=turn_id,
        source=EventSource.VAD,
    )


def agent_interrupted_event(context: RuntimeContext, *, turn_id: UUID) -> Event:
    return build_event(
        context,
        event_type=EventType.AGENT_INTERRUPTED,
        payload=AgentInterruptedPayload(
            interrupted_turn_id=turn_id,
            reason=InterruptReason.USER_SPEECH,
        ),
        turn_id=turn_id,
        source=EventSource.RUNTIME,
    )


def error_event(
    context: RuntimeContext,
    *,
    code: str,
    message: str,
    turn_id: UUID | None = None,
    retryable: bool = False,
) -> Event:
    return build_event(
        context,
        event_type=EventType.ERROR,
        payload=ErrorPayload(code=code, message=message, retryable=retryable),
        turn_id=turn_id,
        source=EventSource.RUNTIME,
    )


def llm_token_event(context: RuntimeContext, *, turn_id: UUID, delta: str) -> Event:
    return build_event(
        context,
        event_type=EventType.LLM_TOKEN,
        payload=LLMTokenPayload(delta=delta),
        turn_id=turn_id,
        source=EventSource.LLM,
    )


def llm_response_event(
    context: RuntimeContext,
    *,
    turn_id: UUID,
    text: str,
    finish_reason: str,
    usage: Usage | None = None,
) -> Event:
    return build_event(
        context,
        event_type=EventType.LLM_RESPONSE,
        payload=LLMResponsePayload(text=text, finish_reason=finish_reason, usage=usage),
        turn_id=turn_id,
        source=EventSource.LLM,
    )
