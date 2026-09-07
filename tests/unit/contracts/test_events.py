from uuid import uuid4

import pytest
from pydantic import ValidationError

from tests.helpers import AGENT_ID, ORG, PROJECT, SESSION_ID, VERSION_ID, utcnow
from xymphony_contracts import (
    AgentInterruptedPayload,
    ErrorPayload,
    Event,
    EventSource,
    EventType,
    InterruptReason,
    LLMTokenPayload,
    SessionStartedPayload,
    TTSChunkPayload,
    UserSpeechStartedPayload,
    validate_sequence_monotonic,
)


def _event(**overrides: object) -> Event:
    turn_id = uuid4()
    data: dict[str, object] = {
        "id": uuid4(),
        "type": EventType.USER_SPEECH_STARTED,
        "timestamp": utcnow(),
        "session_id": SESSION_ID,
        "organization_id": ORG,
        "project_id": PROJECT,
        "agent_id": AGENT_ID,
        "agent_version_id": VERSION_ID,
        "turn_id": turn_id,
        "sequence": 1,
        "source": EventSource.VAD,
        "correlation_id": SESSION_ID,
        "payload": {"vad_confidence": 0.9},
        "schema_version": 1,
    }
    data.update(overrides)
    return Event.model_validate(data)


def test_event_round_trip() -> None:
    event = _event()
    dumped = event.model_dump(mode="json")
    restored = Event.model_validate(dumped)
    assert restored.id == event.id
    assert restored.type == EventType.USER_SPEECH_STARTED
    assert restored.sequence == 1
    assert isinstance(restored.payload, UserSpeechStartedPayload)
    assert restored.turn_id is not None
    assert restored.schema_version == 1


def test_sequence_must_be_at_least_one() -> None:
    with pytest.raises(ValidationError):
        _event(sequence=0)


def test_turn_scoped_event_requires_turn_id() -> None:
    with pytest.raises(ValidationError):
        _event(turn_id=None)


def test_session_started_allows_null_turn_id() -> None:
    event = _event(
        type=EventType.SESSION_STARTED,
        turn_id=None,
        source=EventSource.RUNTIME,
        payload={},
    )
    assert event.turn_id is None
    assert isinstance(event.payload, SessionStartedPayload)


def test_error_may_omit_turn_id() -> None:
    event = _event(
        type=EventType.ERROR,
        turn_id=None,
        source=EventSource.SYSTEM,
        payload={"code": "stt_failed", "message": "disconnected", "retryable": True},
    )
    assert isinstance(event.payload, ErrorPayload)
    assert event.turn_id is None


def test_payload_must_match_type() -> None:
    with pytest.raises(ValidationError):
        _event(type=EventType.LLM_TOKEN, payload={"text": "nope"})


def test_monotonic_sequence_helper() -> None:
    assert validate_sequence_monotonic([1, 2, 3]) is True
    assert validate_sequence_monotonic([1, 3]) is False
    assert validate_sequence_monotonic([0, 1]) is False
    assert validate_sequence_monotonic([]) is False


def test_stale_llm_and_tts_dropped_after_cancel() -> None:
    cancelled = uuid4()
    token = _event(
        type=EventType.LLM_TOKEN,
        turn_id=cancelled,
        source=EventSource.LLM,
        payload=LLMTokenPayload(delta="hi"),
        sequence=10,
    )
    speech = _event(
        type=EventType.USER_SPEECH_STARTED,
        turn_id=uuid4(),
        sequence=11,
        payload=UserSpeechStartedPayload(),
    )
    assert token.is_stale_for_cancelled_turns(frozenset({cancelled})) is True
    assert speech.is_stale_for_cancelled_turns(frozenset({cancelled})) is False


def test_error_is_not_stale_during_cancel() -> None:
    cancelled = uuid4()
    error = _event(
        type=EventType.ERROR,
        turn_id=cancelled,
        source=EventSource.LLM,
        payload=ErrorPayload(code="cancelled", message="turn cancelled", retryable=False),
        sequence=12,
    )
    assert error.is_stale_for_cancelled_turns(frozenset({cancelled})) is False


def test_agent_interrupted_turn_id_matches_payload() -> None:
    turn_id = uuid4()
    event = _event(
        type=EventType.AGENT_INTERRUPTED,
        turn_id=turn_id,
        source=EventSource.RUNTIME,
        payload=AgentInterruptedPayload(
            interrupted_turn_id=turn_id,
            reason=InterruptReason.USER_SPEECH,
            played_text="Hel",
            unplayed_text="lo",
        ),
    )
    assert event.payload.interrupted_turn_id == turn_id  # type: ignore[union-attr]


def test_agent_interrupted_mismatched_turn_rejected() -> None:
    with pytest.raises(ValidationError):
        _event(
            type=EventType.AGENT_INTERRUPTED,
            turn_id=uuid4(),
            source=EventSource.RUNTIME,
            payload=AgentInterruptedPayload(
                interrupted_turn_id=uuid4(),
                reason=InterruptReason.USER_SPEECH,
            ),
        )


def test_unknown_envelope_fields_ignored() -> None:
    event = _event()
    dumped = event.model_dump(mode="json")
    dumped["future_field"] = "ok"
    restored = Event.model_validate(dumped)
    assert restored.id == event.id


def test_tts_chunk_round_trip() -> None:
    event = _event(
        type=EventType.TTS_CHUNK,
        source=EventSource.TTS,
        payload={"audio_ref": "buf:1", "text_range": {"start": 0, "end": 4}},
        sequence=5,
    )
    assert isinstance(event.payload, TTSChunkPayload)
    again = Event.model_validate(event.model_dump(mode="json"))
    assert again.payload.audio_ref == "buf:1"  # type: ignore[union-attr]
