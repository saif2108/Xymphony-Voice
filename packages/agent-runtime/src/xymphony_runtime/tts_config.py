"""Runtime TTS configuration passed into AgentRuntime (not vendor credentials)."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import JsonValue


@dataclass(frozen=True)
class TTSRuntimeConfig:
    provider_key: str
    voice_ref: str
    params: dict[str, JsonValue] = field(default_factory=dict)
