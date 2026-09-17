from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from xymphony_contracts import (
    Agent,
    AgentStatus,
    AgentToolBinding,
    AgentVersion,
    Channel,
    LLMBinding,
    Message,
    STTBinding,
    TTSBinding,
)


class AgentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    status: AgentStatus = AgentStatus.DRAFT
    tags: list[str] = Field(default_factory=list)


class AgentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    status: AgentStatus | None = None
    tags: list[str] | None = None


class AgentListResponse(BaseModel):
    items: list[Agent]
    next_cursor: str | None = None


class AgentVersionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instructions: str = Field(min_length=1, max_length=32_000)
    personality: str = Field(default="", max_length=8_000)
    locale: str = Field(default="en", min_length=2, max_length=16)
    llm: LLMBinding
    stt: STTBinding
    tts: TTSBinding
    tools: list[AgentToolBinding] = Field(default_factory=list)

    @field_validator("tools")
    @classmethod
    def validate_tools(cls, value: list[AgentToolBinding]) -> list[AgentToolBinding]:
        seen: set[str] = set()
        for binding in value:
            name = binding.tool_name
            if name in seen:
                msg = f"duplicate tool binding: {name}"
                raise ValueError(msg)
            seen.add(name)
        return value


class AgentVersionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instructions: str | None = Field(default=None, min_length=1, max_length=32_000)
    personality: str | None = Field(default=None, max_length=8_000)
    locale: str | None = Field(default=None, min_length=2, max_length=16)
    llm: LLMBinding | None = None
    stt: STTBinding | None = None
    tts: TTSBinding | None = None
    tools: list[AgentToolBinding] | None = None

    @field_validator("tools")
    @classmethod
    def validate_tools(cls, value: list[AgentToolBinding] | None) -> list[AgentToolBinding] | None:
        if value is None:
            return value
        seen: set[str] = set()
        for binding in value:
            name = binding.tool_name
            if name in seen:
                msg = f"duplicate tool binding: {name}"
                raise ValueError(msg)
            seen.add(name)
        return value


class AgentVersionListResponse(BaseModel):
    items: list[AgentVersion]
    next_cursor: str | None = None


class SessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: UUID
    agent_version_id: UUID | None = None
    channel: Channel = Channel.PLAYGROUND
    livekit_room: str | None = Field(default=None, max_length=256)


class MessageListResponse(BaseModel):
    items: list[Message]


class HealthResponse(BaseModel):
    status: str
    database: str


class LiveKitTokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    room_name: str
    identity: str
    token: str


# Imported by OpenAPI; UUID alias for path docs
ProjectId = UUID
AgentId = UUID
VersionId = UUID
