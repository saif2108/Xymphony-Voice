"""Session event envelope and P1 payloads. Ordering uses `sequence`, not timestamp."""

from __future__ import annotations

from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    TypeAdapter,
    model_validator,
)

from xymphony_contracts.enums import EventSource, EventType, InterruptReason
from xymphony_contracts.usage import Usage

ENVELOPE_SCHEMA_VERSION = 1

TURN_SCOPED_EVENT_TYPES: frozenset[EventType] = frozenset(
    {
        EventType.AUDIO_FRAME,
        EventType.USER_SPEECH_STARTED,
        EventType.USER_SPEECH_ENDED,
        EventType.TRANSCRIPT_FRAME,
        EventType.LLM_TOKEN,
        EventType.LLM_RESPONSE,
        EventType.TTS_CHUNK,
        EventType.AGENT_INTERRUPTED,
    }
)

STALE_IF_TURN_CANCELLED: frozenset[EventType] = frozenset(
    {
        EventType.LLM_TOKEN,
        EventType.LLM_RESPONSE,
        EventType.TTS_CHUNK,
        EventType.AUDIO_FRAME,
    }
)


class FrozenPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AudioFramePayload(FrozenPayload):
    track: str = Field(min_length=1, max_length=128)
    codec: str = Field(min_length=1, max_length=64)
    duration_ms: int = Field(ge=0)
    data_ref: str | None = Field(default=None, max_length=1024)


class UserSpeechStartedPayload(FrozenPayload):
    vad_confidence: float | None = Field(default=None, ge=0, le=1)


class UserSpeechEndedPayload(FrozenPayload):
    duration_ms: int = Field(ge=0)


class TranscriptFramePayload(FrozenPayload):
    text: str
    is_final: bool
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def end_after_start(self) -> TranscriptFramePayload:
        if self.end_ms < self.start_ms:
            msg = "end_ms must be >= start_ms"
            raise ValueError(msg)
        return self


class LLMTokenPayload(FrozenPayload):
    delta: str


class LLMResponsePayload(FrozenPayload):
    text: str
    finish_reason: str = Field(min_length=1, max_length=64)
    usage: Usage | None = None


class TextRange(FrozenPayload):
    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @model_validator(mode="after")
    def end_after_start(self) -> TextRange:
        if self.end < self.start:
            msg = "text range end must be >= start"
            raise ValueError(msg)
        return self


class TTSChunkPayload(FrozenPayload):
    audio_ref: str = Field(min_length=1, max_length=1024)
    text_range: TextRange | None = None


class AgentInterruptedPayload(FrozenPayload):
    interrupted_turn_id: UUID
    reason: InterruptReason
    played_text: str = ""
    unplayed_text: str = ""


class ErrorPayload(FrozenPayload):
    code: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4000)
    retryable: bool


class SessionStartedPayload(FrozenPayload):
    pass


class SessionEndedPayload(FrozenPayload):
    reason: str = Field(min_length=1, max_length=128)


class TraceContext(FrozenPayload):
    trace_id: str = Field(min_length=1, max_length=64)
    span_id: str = Field(min_length=1, max_length=32)


EventPayload = (
    AudioFramePayload
    | UserSpeechStartedPayload
    | UserSpeechEndedPayload
    | TranscriptFramePayload
    | LLMTokenPayload
    | LLMResponsePayload
    | TTSChunkPayload
    | AgentInterruptedPayload
    | ErrorPayload
    | SessionStartedPayload
    | SessionEndedPayload
)

_PAYLOAD_BY_TYPE: dict[EventType, type[BaseModel]] = {
    EventType.AUDIO_FRAME: AudioFramePayload,
    EventType.USER_SPEECH_STARTED: UserSpeechStartedPayload,
    EventType.USER_SPEECH_ENDED: UserSpeechEndedPayload,
    EventType.TRANSCRIPT_FRAME: TranscriptFramePayload,
    EventType.LLM_TOKEN: LLMTokenPayload,
    EventType.LLM_RESPONSE: LLMResponsePayload,
    EventType.TTS_CHUNK: TTSChunkPayload,
    EventType.AGENT_INTERRUPTED: AgentInterruptedPayload,
    EventType.ERROR: ErrorPayload,
    EventType.SESSION_STARTED: SessionStartedPayload,
    EventType.SESSION_ENDED: SessionEndedPayload,
}


class Event(BaseModel):
    """Canonical event envelope (schema_version=1)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: UUID
    type: EventType
    timestamp: AwareDatetime
    session_id: UUID
    organization_id: UUID
    project_id: UUID
    agent_id: UUID
    agent_version_id: UUID
    deployment_id: UUID | None = None
    turn_id: UUID | None = None
    sequence: int = Field(ge=1)
    source: EventSource
    correlation_id: UUID
    causation_id: UUID | None = None
    payload: EventPayload
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    schema_version: int = Field(default=ENVELOPE_SCHEMA_VERSION, ge=1)
    trace: TraceContext | None = None

    @model_validator(mode="before")
    @classmethod
    def coerce_payload(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        event_type = data.get("type")
        payload = data.get("payload")
        if event_type is None or payload is None or isinstance(payload, BaseModel):
            return data
        try:
            parsed_type = EventType(event_type)
        except ValueError:
            return data
        adapter: TypeAdapter[BaseModel] = TypeAdapter(_PAYLOAD_BY_TYPE[parsed_type])
        data = {**data, "payload": adapter.validate_python(payload)}
        return data

    @model_validator(mode="after")
    def payload_and_turn_rules(self) -> Event:
        expected = _PAYLOAD_BY_TYPE[self.type]
        if type(self.payload) is not expected:
            msg = (
                f"payload type {type(self.payload).__name__} does not match event type {self.type}"
            )
            raise ValueError(msg)
        if self.type in TURN_SCOPED_EVENT_TYPES and self.turn_id is None:
            msg = f"{self.type} requires turn_id (cancellation scope)"
            raise ValueError(msg)
        if self.type == EventType.AGENT_INTERRUPTED:
            interrupted = self.payload
            if isinstance(interrupted, AgentInterruptedPayload):
                if interrupted.interrupted_turn_id != self.turn_id:
                    msg = "AgentInterrupted.turn_id must equal payload.interrupted_turn_id"
                    raise ValueError(msg)
        return self

    def is_stale_for_cancelled_turns(self, cancelled_turn_ids: frozenset[UUID]) -> bool:
        """True when a barge-in should drop this event (runtime ignore predicate)."""
        if self.turn_id is None:
            return False
        if self.type not in STALE_IF_TURN_CANCELLED:
            return False
        return self.turn_id in cancelled_turn_ids


def validate_sequence_monotonic(sequences: list[int]) -> bool:
    """True iff sequences is a consecutive admitted series starting at >= 1."""
    if not sequences or sequences[0] < 1:
        return False
    return all(
        later == earlier + 1 for earlier, later in zip(sequences, sequences[1:], strict=False)
    )
