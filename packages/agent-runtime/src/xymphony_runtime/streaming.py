"""Minimal streaming primitives for future provider output."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class StreamChunkKind(StrEnum):
    LLM_TOKEN = "llm_token"
    LLM_RESPONSE = "llm_response"
    TTS_CHUNK = "tts_chunk"
    TRANSCRIPT_FRAME = "transcript_frame"


@dataclass(frozen=True)
class RuntimeStreamChunk:
    turn_id: UUID
    session_sequence: int
    kind: StreamChunkKind
    payload: str


class IncrementalOutputSink(Protocol):
    async def emit(self, chunk: RuntimeStreamChunk) -> None: ...
