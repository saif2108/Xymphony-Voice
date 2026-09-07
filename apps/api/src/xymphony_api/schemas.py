from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from xymphony_contracts import Agent, AgentStatus, AgentVersion, LLMBinding, STTBinding, TTSBinding


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


class AgentVersionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instructions: str | None = Field(default=None, min_length=1, max_length=32_000)
    personality: str | None = Field(default=None, max_length=8_000)
    locale: str | None = Field(default=None, min_length=2, max_length=16)
    llm: LLMBinding | None = None
    stt: STTBinding | None = None
    tts: TTSBinding | None = None


class AgentVersionListResponse(BaseModel):
    items: list[AgentVersion]
    next_cursor: str | None = None


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
