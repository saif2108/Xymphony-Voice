"""Shared status, channel, and catalog enums. String values match Phase 0 docs."""

from enum import StrEnum


class AgentStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class AgentVersionStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


class SessionStatus(StrEnum):
    INITIALIZING = "initializing"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


class TurnStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMMITTED = "committed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class MessageStatus(StrEnum):
    COMMITTED = "committed"
    INTERRUPTED = "interrupted"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Channel(StrEnum):
    """Transport channel. Prototype 1 uses playground only."""

    PLAYGROUND = "playground"
    WEB_EMBED = "web_embed"
    PUBLIC_API = "public_api"
    TELEPHONY = "telephony"


class ContentPartType(StrEnum):
    TEXT = "text"
    AUDIO_REF = "audio_ref"
    IMAGE = "image"
    FILE = "file"
    VIDEO = "video"


class EventType(StrEnum):
    """P1 event catalog. Names match docs/event-model.md exactly."""

    AUDIO_FRAME = "AudioFrame"
    USER_SPEECH_STARTED = "UserSpeechStarted"
    USER_SPEECH_ENDED = "UserSpeechEnded"
    TRANSCRIPT_FRAME = "TranscriptFrame"
    LLM_TOKEN = "LLMToken"
    LLM_RESPONSE = "LLMResponse"
    TTS_CHUNK = "TTSChunk"
    AGENT_INTERRUPTED = "AgentInterrupted"
    ERROR = "Error"
    SESSION_STARTED = "SessionStarted"
    SESSION_ENDED = "SessionEnded"


class EventSource(StrEnum):
    VAD = "vad"
    STT = "stt"
    RUNTIME = "runtime"
    LLM = "llm"
    TTS = "tts"
    TOOL = "tool"
    WORKFLOW = "workflow"
    TRANSPORT = "transport"
    SYSTEM = "system"


class UsageUnit(StrEnum):
    TOKENS = "tokens"
    CHARACTERS = "characters"
    SECONDS = "seconds"
    BYTES = "bytes"


class InterruptReason(StrEnum):
    USER_SPEECH = "user_speech"


class SessionEndReason(StrEnum):
    USER_STOP = "user_stop"
    MAX_DURATION = "max_duration"
    MAX_TURNS = "max_turns"
    DISCONNECT = "disconnect"
    PROVIDER_FAILED = "provider_failed"
    WORKER_DRAINING = "worker_draining"
    ERROR = "error"
