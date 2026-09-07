"""Runtime LLM configuration passed into AgentRuntime (not vendor credentials)."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import JsonValue


@dataclass(frozen=True)
class LLMRuntimeConfig:
    provider_key: str
    model: str
    system_instructions: str = ""
    params: dict[str, JsonValue] = field(default_factory=dict)
