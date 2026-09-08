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
    # Approximate max input tokens for context budgeting. None disables budgeting.
    max_input_tokens: int | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    top_p: float | None = None
