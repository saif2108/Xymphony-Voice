"""Agent identity and AgentVersion configuration snapshot (P1 subset)."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from json import dumps
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from xymphony_contracts.enums import AgentStatus, AgentVersionStatus
from xymphony_contracts.providers import LLMBinding, STTBinding, TTSBinding


class Agent(BaseModel):
    """Durable product identity. Instructions and providers live on AgentVersion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    status: AgentStatus = AgentStatus.DRAFT
    tags: tuple[str, ...] = ()
    created_by: UUID | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def timestamps_are_aware(self) -> Agent:
        _require_aware(self.created_at, "created_at")
        _require_aware(self.updated_at, "updated_at")
        return self


class AgentVersion(BaseModel):
    """Immutable configuration snapshot loaded by the runtime for a Session.

    Pydantic `frozen=True` encodes snapshot semantics: callers replace the object
    (or persist a new `version_n`) instead of mutating fields in place.
    After `status=published`, control plane must not PATCH this row; that rule is
    enforced by the API later. Runtime always treats this object as read-only.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    agent_id: UUID
    version_n: int = Field(ge=1)
    status: AgentVersionStatus = AgentVersionStatus.DRAFT
    instructions: str = Field(min_length=1, max_length=32_000)
    personality: str = Field(default="", max_length=8_000)
    locale: str = Field(default="en", min_length=2, max_length=16)
    llm: LLMBinding
    stt: STTBinding
    tts: TTSBinding
    config_hash: str | None = None
    created_by: UUID | None = None
    created_at: AwareDatetime
    published_at: AwareDatetime | None = None

    @field_validator("config_hash")
    @classmethod
    def config_hash_is_sha256_hex(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            msg = "config_hash must be a lowercase SHA-256 hex digest"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def published_requires_timestamp(self) -> AgentVersion:
        _require_aware(self.created_at, "created_at")
        if self.published_at is not None:
            _require_aware(self.published_at, "published_at")
        if self.status == AgentVersionStatus.PUBLISHED and self.published_at is None:
            msg = "published AgentVersion requires published_at"
            raise ValueError(msg)
        if self.status != AgentVersionStatus.PUBLISHED and self.published_at is not None:
            msg = "published_at is only valid when status is published"
            raise ValueError(msg)
        return self
    
    def compiled_system_prompt(self) -> str:
         """Join snapshot fields into the LLM system prompt.
 
         Per docs/runtime-design.md #13 ("Prompt compilation"): system =
         join(personality, instructions, goals, constraints, guardrails).
         Only ``personality`` and ``instructions`` exist on this P1 snapshot;
         goals/constraints/guardrails are future fields and are omitted here.
         A blank ``personality`` (the default) contributes nothing, so existing
         versions with no personality set behave exactly as before.
         """
         personality = self.personality.strip()
         instructions = self.instructions.strip()
         if not personality:
             return instructions
         if not instructions:
             return personality
         return f"{personality}\n\n{instructions}"
        
    def compute_config_hash(self) -> str:
        """SHA-256 of canonical config fields (no secrets, no timestamps)."""
        payload = {
            "organization_id": str(self.organization_id),
            "project_id": str(self.project_id),
            "agent_id": str(self.agent_id),
            "version_n": self.version_n,
            "instructions": self.instructions,
            "personality": self.personality,
            "locale": self.locale,
            "llm": self.llm.model_dump(mode="json"),
            "stt": self.stt.model_dump(mode="json"),
            "tts": self.tts.model_dump(mode="json"),
        }
        encoded = dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return sha256(encoded).hexdigest()

    def with_config_hash(self) -> AgentVersion:
        return self.model_copy(update={"config_hash": self.compute_config_hash()})


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        msg = f"{field_name} must be timezone-aware UTC"
        raise ValueError(msg)
